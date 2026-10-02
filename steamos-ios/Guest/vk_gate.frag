#version 450
layout(push_constant) uniform Pattern { uint phase; } pattern;
layout(location = 0) out vec4 color;
void main() {
    uvec2 p = uvec2(gl_FragCoord.xy);
    uvec3 rgb = uvec3((p.x + pattern.phase) & 255u,
                      (p.y + pattern.phase) & 255u,
                      (165u ^ pattern.phase) & 255u);
    color = vec4(vec3(rgb) / 255.0, 1.0);
}
