"""An offscreen OpenGL renderer for a built map.

It draws the glTF file that the pipeline exports, with a sun, a sky gradient and
distance fog. The fog hides the straight edge of the map. There are no shadows, so the
result is a clean picture of the geometry, not a copy of the look of the game.

The renderer needs an OpenGL 3.3 context. macOS, Windows and Linux with a GPU give one.
A container needs Mesa. ``docs/development.md`` holds the packages.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from fpv_maps.materials import srgb_to_linear
from fpv_maps.tour import (
    SKY_HORIZON,
    SKY_ZENITH,
    GroundHeights,
    Pose,
    Tour,
    look_at,
    perspective,
    sun_direction,
)

VERTEX_SHADER = """
#version 330
uniform mat4 mvp;
in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
out vec3 v_world;
out vec3 v_normal;
out vec2 v_uv;
void main() {
    v_world = in_position;
    v_normal = in_normal;
    v_uv = in_uv;
    gl_Position = mvp * vec4(in_position, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330
uniform sampler2D base_texture;
uniform bool use_texture;
uniform bool flat_shading;
uniform vec3 base_color;
uniform vec3 sun_dir;
uniform vec3 eye;
uniform vec2 fog_range;
uniform vec3 fog_color;
uniform vec3 ambient_sky;
uniform vec3 ambient_ground;
in vec3 v_world;
in vec3 v_normal;
in vec2 v_uv;
out vec4 f_color;
void main() {
    vec3 n = flat_shading
        ? normalize(cross(dFdx(v_world), dFdy(v_world)))
        : normalize(v_normal);
    if (dot(n, eye - v_world) < 0.0) {
        n = -n;
    }
    vec3 albedo = use_texture ? pow(texture(base_texture, v_uv).rgb, vec3(2.2)) : base_color;
    float sun = max(dot(n, sun_dir), 0.0);
    vec3 ambient = mix(ambient_ground, ambient_sky, 0.5 + 0.5 * n.y);
    vec3 color = albedo * (sun * vec3(1.08, 1.0, 0.90) * 1.30 + ambient);
    float distance = length(v_world - eye);
    float fog = clamp((distance - fog_range.x) / max(fog_range.y - fog_range.x, 1.0), 0.0, 1.0);
    fog = fog * fog * (3.0 - 2.0 * fog);
    color = mix(color, fog_color, fog);
    f_color = vec4(pow(max(color, 0.0), vec3(1.0 / 2.2)), 1.0);
}
"""

SKY_VERTEX_SHADER = """
#version 330
uniform mat4 inverse_vp;
uniform vec3 eye;
out vec3 v_ray;
void main() {
    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2)) * 2.0 - 1.0;
    vec4 far = inverse_vp * vec4(p, 1.0, 1.0);
    v_ray = far.xyz / far.w - eye;
    gl_Position = vec4(p, 1.0, 1.0);
}
"""

SKY_FRAGMENT_SHADER = """
#version 330
uniform vec3 zenith;
uniform vec3 horizon;
uniform vec3 sun_dir;
in vec3 v_ray;
out vec4 f_color;
void main() {
    vec3 r = normalize(v_ray);
    float up = clamp(r.y * 1.7, 0.0, 1.0);
    vec3 color = mix(horizon, zenith, pow(up, 0.7));
    if (r.y < 0.0) {
        color = mix(horizon, horizon * 0.72, clamp(-r.y * 3.0, 0.0, 1.0));
    }
    float glow = pow(max(dot(r, sun_dir), 0.0), 120.0);
    color += vec3(1.0, 0.93, 0.76) * glow * 0.9;
    f_color = vec4(pow(max(color, 0.0), vec3(1.0 / 2.2)), 1.0);
}
"""


TEMPLATE_COLORS = {
    "asphalt": (92, 90, 86),
    "concrete": (176, 172, 164),
    "brick": (150, 106, 88),
    "plaster": (198, 192, 182),
    "metal": (160, 164, 168),
}
# The plane around a map stands for the land that the map does not hold. It is close
# to the haze color, so that it reads as distance and never as a field of mud.
HORIZON_COLOR = (176, 186, 194)


def _linear(color: tuple[float, float, float]) -> tuple[float, float, float]:
    """One sRGB color, each channel 0.0 to 1.0, to linear light."""
    return tuple(srgb_to_linear(channel * 255.0) for channel in color)  # type: ignore[return-value]


@dataclass
class Geometry:
    """One mesh of the scene, ready for the GPU."""

    name: str
    positions: np.ndarray
    normals: np.ndarray
    uv: np.ndarray
    indices: np.ndarray
    color: tuple[float, float, float]
    texture: Image.Image | None
    flat: bool


def vertex_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Area weighted vertex normals. trimesh needs scipy for this, and the pipeline does not."""
    tri = vertices[faces]
    face = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    out = np.zeros_like(vertices, dtype=np.float64)
    for column in range(3):
        np.add.at(out, faces[:, column], face)
    length = np.linalg.norm(out, axis=1, keepdims=True)
    return np.divide(out, np.maximum(length, 1e-12), dtype=np.float32)


def _base_color(material: object) -> tuple[float, float, float]:
    """The linear base color of a glTF material.

    A material of the game template carries the fallback gray of ``materials.py``,
    because the game replaces it by name at load time. This renderer cannot read the
    game texture, so it substitutes a plausible color for the common names. The result
    tells a concrete wall from an asphalt roof, which one flat gray does not.
    """
    name = str(getattr(material, "name", "") or "")
    for key, rgb in TEMPLATE_COLORS.items():
        if key in name:
            return _linear(tuple(c / 255.0 for c in rgb))
    factor = getattr(material, "baseColorFactor", None)
    if factor is None:
        return (0.25, 0.25, 0.25)
    values = np.asarray(factor, dtype=np.float64).ravel()[:3]
    if values.max() > 1.5:
        values = values / 255.0
    return (float(values[0]), float(values[1]), float(values[2]))


def tall_points(
    geometries: list[Geometry],
    ground: GroundHeights,
    count: int = 3,
    step: float = 8.0,
    apart_m: float = 150.0,
) -> list[tuple[float, float, float]]:
    """The tallest structures of a map: game (x, z) and the height above the terrain.

    A LOD2 chunk holds many buildings in one mesh, so the search runs on a height
    raster, not on single buildings. Every result stands at least ``apart_m`` from the
    results before it, so that one tall block does not give three shots.
    """
    walls = [g.positions for g in geometries if g.flat and g.name != "horizon"]
    if not walls:
        return []
    points = np.concatenate(walls)
    xmin, zmin = float(points[:, 0].min()), float(points[:, 2].min())
    columns = int((points[:, 0].max() - xmin) / step) + 1
    rows = int((points[:, 2].max() - zmin) / step) + 1
    grid = np.full((rows, columns), -1e9, dtype=np.float32)
    cx = np.clip(((points[:, 0] - xmin) / step).astype(np.int64), 0, columns - 1)
    cz = np.clip(((points[:, 2] - zmin) / step).astype(np.int64), 0, rows - 1)
    np.maximum.at(grid, (cz, cx), points[:, 1].astype(np.float32))
    zz, xx = np.mgrid[0:rows, 0:columns]
    terrain = ground.sample(xmin + xx * step, zmin + zz * step)
    above = np.where(grid > -1e8, grid - terrain, 0.0)
    out: list[tuple[float, float, float]] = []
    radius = max(1, int(apart_m / step))
    for _ in range(count):
        index = int(np.argmax(above))
        row, column = divmod(index, columns)
        height = float(above[row, column])
        if height <= 3.0:
            break
        out.append((float(xmin + column * step), float(zmin + row * step), height))
        r0, r1 = max(0, row - radius), min(rows, row + radius + 1)
        c0, c1 = max(0, column - radius), min(columns, column + radius + 1)
        above[r0:r1, c0:c1] = 0.0
    return out


def horizon_plane(bounds: np.ndarray, ground: GroundHeights, reach: float = 12000.0) -> Geometry:
    """A large flat quad around the map, at the height of the map edge.

    Without it a map stands in empty sky, like an island. The quad plus the fog give a
    hazy land horizon. It lies below the lowest terrain point, so it hides nothing.
    """
    low, high = bounds[0], bounds[1]
    center = ((low[0] + high[0]) / 2.0, (low[2] + high[2]) / 2.0)
    y = float(ground.grid.min()) - 3.0
    xs = (center[0] - reach, center[0] + reach)
    zs = (center[1] - reach, center[1] + reach)
    positions = np.array(
        [[xs[0], y, zs[0]], [xs[1], y, zs[0]], [xs[1], y, zs[1]], [xs[0], y, zs[1]]],
        dtype=np.float32,
    )
    return Geometry(
        name="horizon",
        positions=positions,
        normals=np.tile(np.array([0.0, 1.0, 0.0], dtype=np.float32), (4, 1)),
        uv=np.zeros((4, 2), dtype=np.float32),
        indices=np.array([0, 2, 1, 0, 3, 2], dtype=np.uint32),
        color=_linear(tuple(c / 255.0 for c in HORIZON_COLOR)),
        texture=None,
        flat=False,
    )


def load_geometries(glb: Path) -> tuple[list[Geometry], np.ndarray]:
    """Read a glTF binary file into GPU ready meshes and return them with the bounds.

    Terrain keeps its smooth vertex normals. Every other mesh is drawn flat, because a
    LOD2 wall and its roof meet at a hard edge.
    """
    scene = trimesh.load(glb, process=False, force="scene")
    out: list[Geometry] = []
    for name, geom in scene.geometry.items():
        if not isinstance(geom, trimesh.Trimesh) or not len(geom.faces):
            continue
        material = getattr(geom.visual, "material", None)
        texture = getattr(material, "baseColorTexture", None)
        uv = getattr(geom.visual, "uv", None)
        if texture is not None and uv is not None and len(uv) == len(geom.vertices):
            uv_array = np.asarray(uv, dtype=np.float32)
        else:
            texture, uv_array = None, np.zeros((len(geom.vertices), 2), dtype=np.float32)
        flat = "terrain" not in name
        positions = np.asarray(geom.vertices, dtype=np.float32)
        faces = np.asarray(geom.faces, dtype=np.uint32)
        # A flat shaded mesh takes its normal from the screen derivatives, so it needs none.
        normals = (
            np.zeros_like(positions)
            if flat
            else vertex_normals(positions.astype(np.float64), faces.astype(np.int64))
        )
        out.append(
            Geometry(
                name=name,
                positions=positions,
                normals=normals.astype(np.float32),
                uv=uv_array,
                indices=faces.ravel(),
                color=_base_color(material),
                texture=texture,
                flat=flat,
            )
        )
    if not out:
        raise ValueError(f"{glb} holds no mesh")
    low = np.min([g.positions.min(axis=0) for g in out], axis=0)
    high = np.max([g.positions.max(axis=0) for g in out], axis=0)
    return out, np.stack([low, high])


def ground_from_geometries(geometries: list[Geometry], step: float = 4.0) -> GroundHeights:
    """Build the height raster from the terrain meshes, or from everything if there is none."""
    terrain = [g.positions for g in geometries if not g.flat]
    return GroundHeights(np.concatenate(terrain or [g.positions for g in geometries]), step)


def _context(require: int = 330):
    """An offscreen OpenGL context, from the first backend that answers.

    A workstation gives a context with the default backend. A container has no display,
    so the X11 backend of glcontext fails there and EGL with Mesa answers instead.
    """
    try:
        import moderngl
    except ImportError as exc:  # pragma: no cover - depends on the installation
        raise RuntimeError(
            "the renderer needs the tour extra. Run 'uv sync --extra tour'."
        ) from exc

    errors = []
    for backend in (None, "egl", "osmesa"):
        try:
            if backend is None:
                return moderngl.create_context(standalone=True, require=require)
            return moderngl.create_context(standalone=True, require=require, backend=backend)
        except Exception as exc:  # noqa: BLE001 - every backend reports its own error
            errors.append(f"{backend or 'default'}: {exc}")
    raise RuntimeError(
        "no offscreen OpenGL 3.3 context. Install a GPU driver, or Mesa in a container. "
        + " | ".join(errors)
    )


class SceneRenderer:
    """Draws one map into an offscreen buffer, one pose at a time."""

    def __init__(self, glb: Path, tour: Tour, samples: int = 4) -> None:

        self.geometries, self.bounds = load_geometries(glb)
        self.ground = ground_from_geometries(self.geometries)
        self.geometries.append(horizon_plane(self.bounds, self.ground))
        self.tour = tour
        self.ctx = _context(require=330)
        self.program = self.ctx.program(
            vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER
        )
        self.sky = self.ctx.program(
            vertex_shader=SKY_VERTEX_SHADER, fragment_shader=SKY_FRAGMENT_SHADER
        )
        self.sky_vao = self.ctx.vertex_array(self.sky, [])
        size = tour.size
        samples = min(samples, int(self.ctx.info.get("GL_MAX_SAMPLES", 4)))
        self.draw_fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.renderbuffer(size, samples=samples)],
            depth_attachment=self.ctx.depth_renderbuffer(size, samples=samples),
        )
        self.read_fbo = self.ctx.framebuffer(color_attachments=[self.ctx.texture(size, 3)])
        self.vaos = [self._upload(geometry) for geometry in self.geometries]

    def _upload(self, geometry: Geometry) -> tuple[object, object]:
        data = np.hstack([geometry.positions, geometry.normals, geometry.uv]).astype(np.float32)
        vbo = self.ctx.buffer(data.tobytes())
        ibo = self.ctx.buffer(geometry.indices.tobytes())
        vao = self.ctx.vertex_array(
            self.program,
            [(vbo, "3f 3f 2f", "in_position", "in_normal", "in_uv")],
            index_buffer=ibo,
        )
        texture = None
        if geometry.texture is not None:
            # No flip. The first row uploaded is the row that V = 0 samples, and glTF
            # puts V = 0 on the first row of the image, so file order is already right.
            # This used to flip, which cancelled a terrain that numbered V the wrong way
            # round. The two faults hid each other: every tour picture came out right
            # while the exported map, read by a renderer that follows glTF, had its
            # ground mirrored north to south.
            image = geometry.texture.convert("RGB")
            texture = self.ctx.texture(image.size, 3, image.tobytes())
            texture.build_mipmaps()
            texture.anisotropy = 16.0
            import moderngl

            texture.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        return vao, texture

    def fog_for(self, pose: Pose) -> tuple[float, float]:
        """The near and the far distance of the haze, in meters.

        The tour can set both. Without them the haze follows the distance from the
        camera to the subject, so that a shot of one building and a shot of a whole
        city both keep the subject clear and both lose the horizon in haze.
        """
        if self.tour.fog_start_m > 0 and self.tour.fog_end_m > 0:
            return (self.tour.fog_start_m, self.tour.fog_end_m)
        reach = float(np.linalg.norm(np.asarray(pose.eye) - np.asarray(pose.look)))
        return (max(self.tour.fog_start_m, reach * 1.5), max(self.tour.fog_end_m, reach * 8.0))

    def render(self, pose: Pose) -> np.ndarray:
        """Render one pose and return the pixels as a (height, width, 3) uint8 array."""
        import moderngl

        width, height = self.tour.size
        far = float(np.linalg.norm(self.bounds[1] - self.bounds[0])) * 2.0 + 1000.0
        view = look_at(np.asarray(pose.eye, float), np.asarray(pose.look, float))
        projection = perspective(pose.fov_deg, width / height, 1.0, far)
        mvp = (projection @ view).astype(np.float32)
        eye = tuple(float(v) for v in pose.eye)
        sun = sun_direction()
        horizon, zenith = _linear(SKY_HORIZON), _linear(SKY_ZENITH)

        self.draw_fbo.use()
        self.ctx.clear(*horizon, 1.0)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.sky["inverse_vp"].write(np.linalg.inv(mvp).T.astype(np.float32).tobytes())
        self.sky["eye"].value = eye
        self.sky["zenith"].value = zenith
        self.sky["horizon"].value = horizon
        self.sky["sun_dir"].value = sun
        self.sky_vao.render(moderngl.TRIANGLES, vertices=3)

        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.ctx.cull_face = "back"
        self.program["mvp"].write(mvp.T.tobytes())
        self.program["sun_dir"].value = sun
        self.program["eye"].value = eye
        self.program["fog_range"].value = self.fog_for(pose)
        self.program["fog_color"].value = horizon
        self.program["ambient_sky"].value = tuple(
            (0.45 * z + 0.55 * h) * 0.46 for z, h in zip(zenith, horizon, strict=True)
        )
        self.program["ambient_ground"].value = tuple(c * 0.22 for c in horizon)
        for geometry, (vao, texture) in zip(self.geometries, self.vaos, strict=True):
            self.program["flat_shading"].value = geometry.flat
            self.program["use_texture"].value = texture is not None
            self.program["base_color"].value = geometry.color
            if texture is not None:
                texture.use(0)
                self.program["base_texture"].value = 0
            vao.render(moderngl.TRIANGLES)

        self.ctx.copy_framebuffer(self.read_fbo, self.draw_fbo)
        raw = self.read_fbo.read(components=3, alignment=1)
        pixels = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
        return np.flipud(pixels)

    def close(self) -> None:
        self.ctx.release()

    def __enter__(self) -> SceneRenderer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@dataclass
class TourResult:
    """What one tour render wrote."""

    frames: int
    stills: list[Path]
    video: Path | None
    seconds: float


def safe_name(name: str) -> str:
    """Lower case letters, digits and dashes only, for a file name."""
    out = "".join(c if c.isalnum() else "-" for c in name.lower())
    return "-".join(part for part in out.split("-") if part) or "shot"


def _video_writer(path: Path, size: tuple[int, int], fps: int):
    """Open an h264 writer. The frames go to ffmpeg through a pipe, never to disk."""
    import imageio_ffmpeg

    path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio_ffmpeg.write_frames(
        str(path),
        size,
        fps=fps,
        codec="libx264",
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
        macro_block_size=1,
        output_params=["-crf", "20", "-preset", "slow", "-movflags", "+faststart"],
    )
    writer.send(None)
    return writer


def write_tour(
    glb: Path,
    tour: Tour,
    out_dir: Path,
    only: str | None = None,
    video: bool = True,
    seconds: float | None = None,
    on_frame: Callable[[int, int], None] | None = None,
) -> TourResult:
    """Render ``tour`` from ``glb`` into ``out_dir``: one JPEG per shot and one MP4.

    A tour with no shot gets the automatic tour of the map. ``only`` limits the render
    to one shot by name. ``seconds`` scales every shot, so that the whole tour takes
    that long. ``on_frame`` is called with the frame number and the total.
    """
    from fpv_maps.tour import auto_tour, tour_poses

    start = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)

    with SceneRenderer(glb, tour) as renderer:
        plan = tour
        if not plan.shots:
            landmarks = tall_points(renderer.geometries, renderer.ground, count=2)
            shots = auto_tour(
                plan.name,
                (renderer.bounds[0], renderer.bounds[1]),
                renderer.ground,
                landmarks,
            )
            plan = replace(plan, shots=shots.shots)
        if seconds is not None and plan.seconds > 0:
            scale = seconds / plan.seconds
            plan = replace(
                plan, shots=tuple(replace(s, seconds=s.seconds * scale) for s in plan.shots)
            )
        if only is not None:
            kept = tuple(s for s in plan.shots if s.name == only)
            if not kept:
                names = ", ".join(s.name for s in plan.shots)
                raise ValueError(f"no shot is named {only!r}. The tour holds: {names}")
            plan = replace(plan, shots=kept)

        counts = [max(1, int(round(s.seconds * plan.fps))) for s in plan.shots]
        total = sum(counts)
        stills: list[Path] = []
        keepers: dict[int, tuple[int, object]] = {}
        first = 0
        for number, (shot, count) in enumerate(zip(plan.shots, counts, strict=True), start=1):
            keepers[first + min(count - 1, int(round((count - 1) * shot.still_at)))] = (
                number,
                shot,
            )
            first += count

        mp4 = out_dir / f"{plan.name}-tour.mp4"
        writer = _video_writer(mp4, plan.size, plan.fps) if video else None
        try:
            for index, pose in enumerate(tour_poses(plan, renderer.ground)):
                pixels = renderer.render(pose)
                if writer is not None:
                    writer.send(pixels.tobytes())
                if index in keepers:
                    number, shot = keepers[index]
                    name = f"{plan.name}-tour-{number}-{safe_name(shot.name)}.jpg"
                    stills.append(
                        save_still(pixels, out_dir / name, plan.still_px, plan.jpeg_quality)
                    )
                if on_frame is not None:
                    on_frame(index + 1, total)
        finally:
            if writer is not None:
                writer.close()

    return TourResult(
        frames=total,
        stills=stills,
        video=mp4 if video else None,
        seconds=round(time.time() - start, 1),
    )


def save_still(pixels: np.ndarray, path: Path, width: int, quality: int) -> Path:
    """Save one frame as a JPEG of ``width`` pixels, with no metadata."""
    image = Image.fromarray(pixels, mode="RGB")
    if image.width != width:
        height = max(1, round(image.height * width / image.width))
        image = image.resize((width, height), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=quality, optimize=True)
    return path
