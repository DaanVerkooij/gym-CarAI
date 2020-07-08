import gym
import gym_carai
import time
import numpy as np
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # this line forces to run on CPU
import tensorflow as tf
# print(tf.config.experimental.list_physical_devices('GPU') )  # show all gpus
# print(tf.__version__)  # show tf version


def map_to_range(x, min_out=-1, max_out=1) :
    # custom
    x_out = tf.keras.backend.tanh(x)  # x in range(-1,1)
    scale = (max_out-min_out)/2.
    min_out += 1
    return  x_out * scale + min_out


class Memory:
    def __init__(self):
        self.states = []
        self.actions = []
        self.rewards = []
        self.JStar = []

    def store(self, state, action, reward, JOpt):
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.JStar.append(JOpt)

    def clear(self):
        self.states = []
        self.actions = []
        self.rewards = []
        self.JStar = []


class CriticModel(tf.keras.Model):
    def __init__(self, learning_rate, observation_shape):
        super(CriticModel, self).__init__()

        # critic part of model (value function)
        self.inner1 = tf.keras.layers.Dense(100, activation='relu')
        self.value = tf.keras.layers.Dense(observation_shape) # condense back into 2

        self.opt = tf.keras.optimizers.Adamax(learning_rate)
        # self.opt = tf.compat.v1.train.AdamOptimizer(learning_rate, use_locking=True)

    def call(self, inputs):
        x = self.inner1(inputs)
        J = self.value(x)
        return J


class ActorModel(tf.keras.Model):
    def __init__(self, learning_rate, observation_shape):
        super(ActorModel, self).__init__()
        self.observation_shape = observation_shape

        # actor part of Model (policies)
        self.inner1 = tf.keras.layers.Dense(100, activation='relu')
        self.turning = tf.keras.layers.Dense(1, activation=map_to_range)  # sigmoid for turning direction

        self.opt = tf.keras.optimizers.Adamax(learning_rate)

    def call(self, inputs):
        x = self.inner1(inputs)
        dir = self.turning(x)
        return dir


def get_loss_critic(Critic, memory, gamma=0.99):
    # get value for each timestep
    values = Critic(tf.convert_to_tensor(np.vstack(memory.actions), dtype=tf.float32))

    # Try #1: like in cartpole
    v = 1
    if v == 1:
        # This is based on the assumption that reward evaluates how good current state is
        # gamma is the forgetting factor, prioritize short term rewards over long term.
        reward_sum = 0
        discounted_rewards = []
        for reward in memory.rewards[::-1]:
            reward_sum = reward + gamma * reward_sum
            discounted_rewards.append(reward_sum)
        discounted_rewards = discounted_rewards[::-1]
        # get J for each timestep
        advantage = tf.convert_to_tensor(np.array(discounted_rewards)[:, None], dtype=tf.float32) - values
        critic_loss = advantage ** 2
    elif v == 2:
        # Try #2: like in slides - currently does not work with gradientTape
        obs_size = len(memory.states[1][0])
        ecs = []
        for i in range(len(memory.rewards))[:-1]:
            ec = values[i+1] - (gamma * values[i] - memory.rewards[i])
            ecs.append(ec)
        # get J for each timestep
        ecs = tf.convert_to_tensor(np.array(ecs)[:, None], dtype=tf.float32)
        critic_loss = ecs ** 2
    elif v == 3:
        # Try #3: hybrid
        # discount the rewards based on 'R_t = sum gamma^(k-t) r_k(s_k, a_k)
        gamma_mag = gamma
        reward_sum = 0
        discounted_rewards = []
        for reward in memory.rewards[::-1]:
            gamma_mag = gamma*gamma_mag
            discounted_rewards.append(reward*gamma_mag)
        # discounted_rewards = discounted_rewards[::-1]  # get original order
        # get J for each timestep
        advantage = tf.convert_to_tensor(np.array(discounted_rewards)[:, None], dtype=tf.float32) - values
        critic_loss = advantage ** 2
    critic_loss = tf.reduce_mean(critic_loss)
    return critic_loss, discounted_rewards


def get_loss_actor(Actor, Critic, memory):
    # get value for each timestep, based on the reward derived from the critic.
    # get critic reward through actor response to allow gradienttape to get the differences.
    values = Critic(Actor(tf.convert_to_tensor(np.vstack(memory.states), dtype=tf.float32)))
    # get J for each timestep
    err = values - tf.convert_to_tensor(np.array(memory.JStar)[:, None], dtype=tf.float32)
    actor_loss = err ** 2
    actor_loss = tf.reduce_mean(actor_loss)
    return actor_loss


# Setup for training etc.
env = gym.make('carai-simple-v0')  # First open the environment

observation_shape = env.observation_space.shape[0]

start_time = time.time()           # Register current time
epoch = 1                          # Current episode
maxEpoch = 100                     # max amount of epochs
maxEpochTime = 500                 # [s] max seconds to spend per epoch
dt = 1/60                          # fps (should equal monitor refresh rate)
maxSteps = int(maxEpochTime/dt)    # max duration of an epoch
Terminate = None
done = 0
learning_rate = 0.001
mem = Memory()
run = True
Actor = ActorModel(learning_rate, observation_shape)  # global network
Critic = CriticModel(learning_rate, observation_shape)  # global network
maxRewardSoFar = -90000

rewardavglist = []
criticavglist = []

while run:
    print("--- starting run %s ---" % epoch)
    run_time = time.time()
    env.reset()
    mem.clear()

    # initial values
    epoch_loss = 0
    action = np.array([0])
    obs, reward, done, info_dict, Terminate = env.step(action, dt)

    for i in range(maxSteps):
        # calculate next step
        env.render('human')  # manual, human, rgb_array
        action = Actor(obs).numpy()[0]  # returns 0,1,2, action space = -1 to 1
        obs, reward, done, info_dict, Terminate = env.step(action, dt)
        mem.store(obs, action[0], reward, info_dict['JStar'])
        if Terminate:  # Window was closed.
            epoch = maxEpoch*2
            run = False
        if done:
            break

    if not Terminate:
        # GradientTape tracks the gradient of all variables within scope, useful for optimizer
        with tf.GradientTape() as critic_tape:
            critic_loss, critic_rewards = get_loss_critic(Critic, mem)
        # Apply found gradients to model
        critic_grads = critic_tape.gradient(critic_loss, Critic.trainable_weights)
        Critic.opt.apply_gradients(zip(critic_grads, Critic.trainable_weights))

        with tf.GradientTape() as actor_tape:
            actor_loss = get_loss_actor(Actor, Critic, mem)
        actor_grads = actor_tape.gradient(actor_loss, Actor.trainable_weights)
        Actor.opt.apply_gradients(zip(actor_grads, Actor.trainable_weights))

        print("--- Actor loss {} - ".format(actor_loss))
        print("--- Critic loss {} - ".format(critic_loss))
    print("--- %s seconds ---" % (time.time() - run_time))

    epoch += 1

    # Statistics for training evaluation
    rewardavg = sum(mem.rewards)/len(mem.rewards)
    criticavg = sum(critic_rewards)/len(critic_rewards)
    rewardavglist.append(rewardavg)
    criticavglist.append(criticavg)
    if rewardavg > maxRewardSoFar:
        maxRewardSoFar = rewardavg
        correspCritic  = criticavg
    print("- Highest reward yet {} - {} - ".format(maxRewardSoFar,correspCritic))
    print("- Most recent run reward {} - {} - ".format(rewardavg,criticavg))
    if len(rewardavglist)>11:
        last = rewardavglist[-10:]
        last2 = criticavglist[-10:]
        print("- Last ten runs average {}, - {} - ".format(sum(last)/len(last),sum(last2)/len(last2)))
env.close()
print("--- total %s seconds ---" % (time.time() - start_time))
