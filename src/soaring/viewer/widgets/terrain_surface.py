"""One DEM mesh, displayed with elevation colours or a georeferenced orthophoto."""

from __future__ import annotations

import pyqtgraph.opengl as gl
from OpenGL import GL
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage
from PyQt6.QtOpenGL import QOpenGLTexture
from pyqtgraph.opengl.shaders import FragmentShader, ShaderProgram, VertexShader

ORTHOPHOTO_SHADER = ShaderProgram(
    "soaring_orthophoto",
    [
        VertexShader("""#version 140
            uniform mat4 u_mvp;
            uniform float u_bounds[4];
            in vec4 a_position;
            out vec2 v_texcoord;
            void main() {
                gl_Position = u_mvp * a_position;
                // Image row zero is north. Do not flip or transpose the photo.
                v_texcoord = vec2(
                    (a_position.x - u_bounds[0]) / (u_bounds[2] - u_bounds[0]),
                    (u_bounds[3] - a_position.y) / (u_bounds[3] - u_bounds[1])
                );
            }
        """),
        FragmentShader("""#version 140
            uniform sampler2D u_texture;
            in vec2 v_texcoord;
            out vec4 fragColor;
            void main() {
                fragColor = texture(u_texture, v_texcoord);
            }
        """),
    ],
)


class TerrainSurface(gl.GLSurfacePlotItem):
    """Keep the DEM geometry while changing its surface appearance in place."""

    def __init__(self, *, image=None, **kwargs):
        """Retain the north-up RGB image and upload it only in photo mode."""
        super().__init__(**kwargs)
        self._image = image
        self._texture = None
        self._aerial = False
        self._bounds = [
            kwargs["x"][0],
            kwargs["y"][0],
            kwargs["x"][-1],
            kwargs["y"][-1],
        ]

    def set_aerial(self, enabled):
        """Switch shaders without changing vertices, heights or camera state."""
        self._aerial = bool(enabled and self._image is not None)
        self.setShader(ORTHOPHOTO_SHADER if self._aerial else "shaded")

    def release_texture(self):
        """Release GPU storage while the view's shared context is current."""
        if self._texture is not None:
            self._texture.destroy()
            self._texture = None

    def _upload_texture(self):
        """Upload RGB imagery once; mipmaps keep distant views stable."""
        data = self._image
        height, width = data.shape[:2]
        image = QImage(
            data.data, width, height, data.strides[0], QImage.Format.Format_RGB888
        )
        limit = int(GL.glGetIntegerv(GL.GL_MAX_TEXTURE_SIZE))
        if max(width, height) > limit:
            image = image.scaled(
                limit,
                limit,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._texture = QOpenGLTexture(
            image, QOpenGLTexture.MipMapGeneration.GenerateMipMaps
        )
        self._texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
        self._texture.setMinMagFilters(
            QOpenGLTexture.Filter.LinearMipMapLinear, QOpenGLTexture.Filter.Linear
        )

    def paint(self):
        """Sample the orthophoto by local east/north coordinates on each triangle."""
        if not self._aerial:
            super().paint()
            return
        if self._texture is None:
            self._upload_texture()
        ORTHOPHOTO_SHADER["u_bounds"] = self._bounds
        # GLSL initializes the sampler uniform to texture unit zero.
        GL.glActiveTexture(GL.GL_TEXTURE0)
        self._texture.bind()
        try:
            super().paint()
        finally:
            self._texture.release()
