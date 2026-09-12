@tool
extends TextureRect
## Space outside the energy icon, in card-local pixels.
@export_range(0.0, 100.0) var glow_margin: float = 30.0
@export_range(0.0, 3.0) var transition_duration: float = 0.5
@export var active: bool = true
var _transition: Tween

func _ready() -> void:
	# Keep the saved material shared while editing; isolate animation in play mode.
	if not Engine.is_editor_hint():
		material = material.duplicate()
	material.set_shader_parameter("activation", 1.0 if active else 0.0)
	visible = active

func set_icon_size(icon_size: Vector2) -> void:
	size = icon_size + Vector2.ONE * glow_margin * 2.0
	material.set_shader_parameter("icon_size", icon_size)
	material.set_shader_parameter("canvas_size", size)

func set_active(value: bool, animate: bool = true) -> void:
	if _transition:
		_transition.kill()
	active = value
	if value:
		show()
	var target := 1.0 if value else 0.0
	if not animate or transition_duration <= 0.0:
		material.set_shader_parameter("activation", target)
		visible = value
		return
	_transition = create_tween()
	_transition.tween_method(_set_activation, float(material.get_shader_parameter("activation")), target, transition_duration).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	if not value:
		_transition.tween_callback(hide)

func _set_activation(value: float) -> void:
	material.set_shader_parameter("activation", value)
