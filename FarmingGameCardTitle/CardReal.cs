using Godot;
using System;
using System.Linq;


public partial class CardReal : Control
{
	public enum State {BASE, CLICKED, DRAGGING, AIMING, RELEASED};
	public State current; 
	
	public Godot.Collections.Dictionary<State, CardState> States;
	
	// FIX IN A BIT
	// Called when the node enters the scene tree for the first time.
	public override void _Ready(){
		current = State.BASE;
	}
	public void _OnBodyEnter(){
		GD.Print("Elatedd");
	}

}
