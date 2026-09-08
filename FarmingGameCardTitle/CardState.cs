using Godot;
using System;

public partial class CardState : Node
{
	// Called when the node enters the scene tree for the first time.
	public enum State {BASE, CLICKED, DRAGGING, AIMING, RELEASED};
	public CanvasLayer cardUI;

	[Export] public State childState;
	public override void _Ready()
	{
	}

	// Called every frame. 'delta' is the elapsed time since the previous frame.
	public override void _Process(double delta)
	{
	}
	public void EnterState(){
		
	}
	public void ExitState(){
		
	}
	public void OnInput(){

	}
	public void OnGUIInput(){

	}
	public void OnMouseEnter(){

	}
	public void OnMouseExit(){

	}
}
