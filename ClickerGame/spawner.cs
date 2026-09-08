using Godot;
using System;

public partial class spawner : Node2D
{
	[Export]
    public PackedScene MobScene { get; set; }

	private int token;
	// Called when the node enters the scene tree for the first time.
	public override void _Ready()
	{
		token = 0;
	}

	// Called every frame. 'delta' is the elapsed time since the previous frame.
	public override void _Process(double delta)
	{
		if(token == 300){
			John mob = MobScene.Instantiate<John>();

			token = 0;
		}
		token += 1;
	}
}
