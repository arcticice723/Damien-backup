import unittest

from jarvis_assistant.mascot_ui import (
    FLOATING_MASCOT_SHOW_LABELS,
    MASCOT_CANVAS_SIZE,
    MASCOT_WIDGET_SIZE,
    MASCOT_ASSET_RELATIVE_PATH,
    SMOOTH_RENDER_SCALE,
    TRANSPARENT_MASCOT_BG,
    accent_hex,
    alienware_motion_state,
    butler_mascot_shapes,
    header_emblem_shapes,
    hybrid_dark_theme,
    mascot_dimensions,
    mascot_start_position,
    mascot_widget_status,
    render_mascot_asset_image,
)


class MascotUiTests(unittest.TestCase):
    def test_hybrid_theme_uses_cinematic_but_readable_accents(self):
        colors = hybrid_dark_theme()

        self.assertEqual(colors["bg"], "#070b10")
        self.assertEqual(colors["accent"], "#48d1b2")
        self.assertEqual(colors["warning"], "#d9a441")
        self.assertEqual(colors["speaker"], "#7fdcff")

    def test_butler_mascot_shape_plan_is_floating_companion_not_boxed_pixel_art(self):
        shapes = butler_mascot_shapes("#48d1b2", engine_on=True, mic_on=False)
        names = {shape["name"] for shape in shapes}

        self.assertGreater(MASCOT_WIDGET_SIZE[0], 148)
        self.assertIn("companion_shadow", names)
        self.assertIn("soft_jacket", names)
        self.assertIn("accent_cravat", names)
        self.assertIn("listening_eye", names)
        self.assertIn("muted_eye", names)
        self.assertNotIn("aura_outer", names)
        self.assertNotIn("monocle", names)
        self.assertNotIn("tailcoat_left", names)

    def test_mascot_window_uses_transparent_background_key(self):
        self.assertEqual(TRANSPARENT_MASCOT_BG, "#010203")

    def test_motion_state_changes_with_phase_and_assistant_state(self):
        idle = alienware_motion_state(0, "idle")
        listening = alienware_motion_state(12, "listening")
        thinking = alienware_motion_state(12, "thinking")

        self.assertEqual(idle["bob"], 0)
        self.assertGreater(listening["glow_width"], idle["glow_width"])
        self.assertGreater(thinking["pulse"], listening["pulse"])

    def test_animated_mascot_shapes_shift_the_companion_without_boxing_it(self):
        resting = butler_mascot_shapes("#48d1b2", engine_on=True, mic_on=True, phase=0, state="idle")
        moving = butler_mascot_shapes("#48d1b2", engine_on=True, mic_on=True, phase=10, state="idle")

        resting_face = next(shape for shape in resting if shape["name"] == "face")
        moving_face = next(shape for shape in moving if shape["name"] == "face")

        self.assertNotEqual(resting_face["coords"], moving_face["coords"])
        self.assertTrue(any(shape["name"] == "animated_glow_ring" for shape in moving))
        self.assertFalse(any(shape["kind"] == "rectangle" for shape in moving))

    def test_header_emblem_uses_same_motion_language(self):
        shapes = header_emblem_shapes("#48d1b2", phase=8, state="thinking")
        names = {shape["name"] for shape in shapes}

        self.assertIn("header_glow", names)
        self.assertIn("header_head", names)
        self.assertIn("header_status_eye", names)

    def test_mascot_smooth_render_uses_supersampling_for_antialiasing(self):
        self.assertGreaterEqual(SMOOTH_RENDER_SCALE, 4)

    def test_smooth_mascot_image_returns_antialiased_rgba_sprite(self):
        from jarvis_assistant.mascot_ui import smooth_mascot_image

        image = smooth_mascot_image("#48d1b2", engine_on=True, mic_on=True, phase=8, state="idle", scale=1.0)

        self.assertEqual(image.mode, "RGBA")
        self.assertEqual(image.size, MASCOT_CANVAS_SIZE)
        alpha_histogram = image.getchannel("A").histogram()
        self.assertTrue(any(alpha_histogram[1:255]))

    def test_butler_sprite_asset_path_points_to_generated_asset(self):
        self.assertEqual(MASCOT_ASSET_RELATIVE_PATH.as_posix(), "assets/mascot/damien_butler_v2.png")

    def test_asset_renderer_preserves_full_body_sprite_inside_widget_canvas(self):
        from PIL import Image, ImageDraw

        source = Image.new("RGBA", (120, 240), (0, 0, 0, 0))
        draw = ImageDraw.Draw(source)
        draw.ellipse((35, 5, 85, 55), fill=(240, 210, 180, 255))
        draw.rectangle((42, 55, 78, 170), fill=(20, 20, 24, 255))
        draw.rectangle((45, 170, 58, 230), fill=(20, 20, 24, 255))
        draw.rectangle((64, 170, 77, 230), fill=(20, 20, 24, 255))

        rendered = render_mascot_asset_image(source, phase=6, state="idle", scale=1.0)

        self.assertEqual(rendered.mode, "RGBA")
        self.assertEqual(rendered.size, MASCOT_CANVAS_SIZE)
        self.assertIsNotNone(rendered.getbbox())

    def test_asset_renderer_uses_widget_safe_hard_alpha_edges(self):
        from PIL import Image, ImageDraw

        source = Image.new("RGBA", (80, 160), (0, 0, 0, 0))
        draw = ImageDraw.Draw(source)
        draw.ellipse((5, 5, 75, 155), fill=(32, 32, 38, 180))

        rendered = render_mascot_asset_image(source, phase=0, state="idle", scale=1.0)
        alpha_values = set(rendered.getchannel("A").histogram()[1:255])

        self.assertEqual(alpha_values, {0})

    def test_widget_canvas_uses_full_widget_space_without_text_labels(self):
        self.assertEqual(MASCOT_CANVAS_SIZE, MASCOT_WIDGET_SIZE)
        self.assertFalse(FLOATING_MASCOT_SHOW_LABELS)

    def test_accent_palette_supports_named_and_custom_colors(self):
        self.assertEqual(accent_hex("gold", ""), "#d9a441")
        self.assertEqual(accent_hex("custom", "#ffcc66"), "#ffcc66")
        self.assertEqual(accent_hex("custom", "not-a-color"), "#48d1b2")

    def test_theme_applies_accent_and_reduced_glow(self):
        colors = hybrid_dark_theme(accent="#d9a441", style="jarvis", reduce_glow=True)

        self.assertEqual(colors["accent"], "#d9a441")
        self.assertEqual(colors["accent_dark"], "#9b7530")
        self.assertEqual(colors["line"], "#2d3742")

    def test_mascot_dimensions_support_qol_sizes(self):
        self.assertLess(mascot_dimensions("small")[0], MASCOT_WIDGET_SIZE[0])
        self.assertEqual(mascot_dimensions("normal"), MASCOT_WIDGET_SIZE + (1.0,))
        self.assertGreater(mascot_dimensions("large")[0], MASCOT_WIDGET_SIZE[0])

    def test_mascot_start_position_defaults_near_lower_right_and_clamps_saved_values(self):
        self.assertEqual(mascot_start_position(None, None, 184, 226, 1920, 1080), (1700, 758))
        self.assertEqual(mascot_start_position(4000, -50, 184, 226, 1920, 1080), (1736, 0))

    def test_mascot_widget_status_prioritizes_activity_and_offline_label(self):
        self.assertEqual(
            mascot_widget_status(streaming_active=True, wake_on=True, mic_on=True, engine_on=True),
            ("Thinking", "#f1b84b"),
        )
        self.assertEqual(
            mascot_widget_status(streaming_active=False, wake_on=False, mic_on=False, engine_on=False),
            ("Local AI...", "#d35c6a"),
        )


if __name__ == "__main__":
    unittest.main()
