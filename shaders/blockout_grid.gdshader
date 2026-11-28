// AFTERLIGHT — Blockout grid shader.
// Draws a 1-metre grid (with a stronger line every 5 m) in WORLD space,
// so scale is readable anywhere in the level while we use placeholder geometry.
// Works in Forward+, Mobile and Compatibility renderers.
shader_type spatial;

uniform vec4 base_color : source_color = vec4(0.55, 0.56, 0.58, 1.0);
uniform vec4 line_color : source_color = vec4(0.25, 0.26, 0.28, 1.0);
uniform float minor_size = 1.0;     // metres between thin lines
uniform float major_every = 5.0;    // a thick line every N minor cells
uniform float line_width = 0.02;    // metres
uniform float roughness_value : hint_range(0.0, 1.0) = 0.85;
uniform bool show_grid = true;

varying vec3 world_pos;
varying vec3 world_normal;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

// Returns 1.0 on a grid line, 0.0 elsewhere, anti-aliased with fwidth.
float grid_2d(vec2 p, float cell, float width) {
	vec2 g = abs(fract(p / cell - 0.5) - 0.5) * cell;
	vec2 aa = fwidth(p) * 1.5;
	vec2 l = 1.0 - smoothstep(vec2(width) - aa, vec2(width) + aa, g);
	return max(l.x, l.y);
}

float grid_tri(vec3 p, vec3 n, float cell, float width) {
	vec3 w = abs(n);
	w = w / (w.x + w.y + w.z);
	return grid_2d(p.yz, cell, width) * w.x
		+ grid_2d(p.xz, cell, width) * w.y
		+ grid_2d(p.xy, cell, width) * w.z;
}

void fragment() {
	vec3 col = base_color.rgb;
	if (show_grid) {
		float minor = grid_tri(world_pos, world_normal, minor_size, line_width * 0.5);
		float major = grid_tri(world_pos, world_normal, minor_size * major_every, line_width);
		col = mix(col, line_color.rgb, clamp(minor * 0.35 + major * 0.8, 0.0, 1.0));
	}
	ALBEDO = col;
	ROUGHNESS = roughness_value;
	METALLIC = 0.0;
}
