shader_type canvas_item;
render_mode blend_add;

uniform float radius_expansion : hint_range(0.0, 60.0) = 10.0;
uniform float ease : hint_range(0.001, 0.04) = 0.008;
uniform float modulo_width : hint_range(0.001, 0.1) = 0.02;
uniform float width : hint_range(0.001, 0.3) = 0.075;
uniform float ripple_speed : hint_range(0.0, 0.3) = 0.04;
// Rainbow follows the circumference; radial motion remains independent.
uniform sampler2D rainbow_gradient : source_color, filter_linear, repeat_disable;
uniform float rainbow_saturation : hint_range(0.0, 1.0) = 0.85;
uniform float rainbow_brightness : hint_range(0.0, 2.0) = 0.85;
uniform float rainbow_offset : hint_range(0.0, 1.0) = 0.0;
uniform float rainbow_rotation_speed : hint_range(-0.2, 0.2) = 0.0;
uniform float activation : hint_range(0.0, 1.0) = 1.0;
uniform vec2 icon_size = vec2(64.0);
uniform vec2 canvas_size = vec2(124.0);

vec4 rainbow_color(float hue) {
	vec4 sampled = texture(rainbow_gradient, vec2(hue, 0.5));
	vec3 color = mix(vec3(1.0), sampled.rgb, rainbow_saturation) * rainbow_brightness;
	return vec4(color, sampled.a);
}

void fragment() {
	// Analytic equivalent of the previous generated circular distance texture.
	float radius = min(icon_size.x, icon_size.y) * 0.5 + radius_expansion;
	float outer_space = max(min(canvas_size.x, canvas_size.y) * 0.5 - radius, 0.001);
	vec2 centered = (UV - vec2(0.5)) * canvas_size;
	float distance_from_center = length(centered);
	float angle = atan(centered.y, centered.x);
	float hue = fract(angle / 6.28318530718 + rainbow_offset - TIME * rainbow_rotation_speed);
	float sdf = clamp(1.0 - max(0.0, distance_from_center - radius) * width / outer_space, 0.0, 1.0);
	vec4 tint = COLOR;
	float alpha = sdf * tint.a;
	float phase = mod(TIME * ripple_speed + alpha, modulo_width);
	float brightness = alpha - phase + smoothstep(0.0, ease, phase) * modulo_width;
	float visible_width = width * activation;
	float opacity = smoothstep(1.0 - max(visible_width, 0.000001), 1.0, brightness);
	vec4 rainbow = rainbow_color(hue);
	COLOR = vec4(rainbow.rgb * tint.rgb * sdf * sdf, rainbow.a * opacity * step(0.000001, activation));
}
