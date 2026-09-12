extends Control
var enabled := true
var overlapping := false
func _ready():
	for i in range(1, 3):
		var card = $Cards/Card.duplicate()
		card.name = "Card%d" % (i + 1)
		var old = card.get_node("Glow")
		card.remove_child(old)
		old.free()
		var glow = load("res://RDMod/Visuals/OverdriveCostGlow.tscn").instantiate()
		glow.name = "Glow"
		card.add_child(glow)
		card.move_child(glow, 0)
		$Cards.add_child(card)
		card.position.x = 285.0 * i
	$Cards/Card3.rotation_degrees = 10.0
	for card in $Cards.get_children():
		var icon = card.get_node("EnergyIcon")
		var glow = card.get_node("Glow")
		glow.position = icon.position - Vector2.ONE * glow.glow_margin
		glow.set_icon_size(icon.size)
func _unhandled_key_input(event):
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_SPACE:
			enabled = not enabled
			for card in $Cards.get_children():
				card.get_node("Glow").set_active(enabled)
		KEY_O:
			overlapping = not overlapping
			$Cards/Card2.position.x = 150.0 if overlapping else 285.0
			$Cards/Card3.position.x = 300.0 if overlapping else 570.0
		KEY_EQUAL, KEY_PLUS, KEY_KP_ADD:
			$Cards.scale = Vector2.ONE * minf($Cards.scale.x + 0.1, 1.5)
		KEY_MINUS, KEY_KP_SUBTRACT:
			$Cards.scale = Vector2.ONE * maxf($Cards.scale.x - 0.1, 0.6)
