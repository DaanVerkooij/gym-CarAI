import pyglet
import numpy as np


class Viewer():
    def __init__(self, width, height, vsync, manualControl=False):
        self.width = width
        self.height = height
        config = pyglet.gl.Config(sample_buffers=1, samples=4)
        self.window = pyglet.window.Window(width=self.width, height=self.height)
        self.vsync = vsync
        self.window.set_vsync(vsync)
        self.is_open = open
        self.toDraw = []
        self.score_label = None
        self.track_label = None
        self.time_label = None
        self.episode_label = None
        self.Terminate = None
        self.window.on_close = self.window_closed
        pyglet.gl.glClearColor(1, 1, 1, 1)

    def render(self, return_rgb_array=False):
        self.window.clear()
        self.window.dispatch_events()
        if self.vsync:  # make prettier since framerate does not need to be maximized
            pyglet.gl.glEnable(pyglet.gl.GL_BLEND)
            pyglet.gl.glEnable(pyglet.gl.GL_LINE_SMOOTH)
            pyglet.gl.glHint(pyglet.gl.GL_LINE_SMOOTH_HINT, pyglet.gl.GL_DONT_CARE)
        for batch in self.toDraw:
            batch.draw()

        # write rgb array as in done in OpenAI classic control framework
        arr = None
        if return_rgb_array:
            buffer = pyglet.image.get_buffer_manager().get_color_buffer()
            image_data = buffer.get_image_data()
            arr = np.frombuffer(image_data.get_data(), dtype=np.uint8)
            arr = arr.reshape(buffer.height, buffer.width, 4)
            arr = arr[::-1, :, 0:3]
        elif self.is_open:
            self.window.flip()
        return arr if return_rgb_array else self.is_open

    def window_closed(self):
        self.Terminate = 1
        self.close()

    def close(self):
        if self.is_open:
            self.window.close()
            self.is_open = False

    def labels(self, main_batch, label_font_size, track_name, time, episode):
        if track_name is not None:
            self.track_label = pyglet.text.Label(text="Current Track:" + track_name,
                                                 font_name='Times New Roman',
                                                 font_size=label_font_size * 0.5,
                                                 x=0.5 * label_font_size,
                                                 y=self.height - 1.2 * label_font_size,
                                                 anchor_x='left', anchor_y='center',
                                                 color=(100, 0, 100, 255),
                                                 batch=main_batch)

        if time is not None:
            self.time_label = pyglet.text.Label(text="Current Episode Time:" + str(time),
                                                font_name='Times New Roman',
                                                font_size=label_font_size * 0.5,
                                                x=0.5 * label_font_size,
                                                y=self.height - 1.8 * label_font_size,
                                                anchor_x='left', anchor_y='center',
                                                color=(100, 0, 100, 255),
                                                batch=main_batch)

        if episode is not None:
            self.episode_label = pyglet.text.Label(text="Current episode:" + str(episode),
                                                   font_name='Times New Roman',
                                                   font_size=label_font_size * 0.5,
                                                   x=0.5 * label_font_size,
                                                   y=self.height - 2.4 * label_font_size,
                                                   anchor_x='left', anchor_y='center',
                                                   color=(100, 0, 100, 255),
                                                   batch=main_batch)

        return self.track_label, self.time_label, self.episode_label


