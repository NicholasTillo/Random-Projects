using Godot;
using System;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;

public partial class main : Node
{
	// Called when the node enters the scene tree for the first time.

	[Export]
	public PackedScene NeurtalScene { get; set; }

	public int score = 0;


	[Export]
	public PackedScene ButtonInstantiated { get; set; }

	public override void _Ready()
	{
		NewGame();
		


	}
	

	// Called every frame. 'delta' is the elapsed time since the previous frame.
	public override void _Process(double delta)
	{
	}
	public void NewGame(){
		//jsonHolder = 
		InstantiateFarm(20);
	}
	public void InstantiateFarm(int squares){

		int cols = 4;
		int rows = 4;
		Vector2 topLeftFarm = new Vector2(150,50);
		Rect2 rect = GetNode<CollisionShape2D>("Farm/CollisionShape2D").Shape.GetRect();
		
		float colSpaceSize = rect.Size.Y /cols *(float) 0.7777777777; 
		float rowSpaceSize = rect.Size.X /rows; 
				
		

		float paddingY = colSpaceSize / 2;
		float paddingX = rowSpaceSize / 2;

		for(int i = 0; i < squares/cols; i++){
			for(int j = 0; j < cols; j++){
				Neutral NameName = NeurtalScene.Instantiate<Neutral>();
				GD.Print(NameName);	
				
				var spawnLocation = new Vector2(rowSpaceSize * j + paddingX,colSpaceSize * i + paddingY) * 25;
				NameName.Position = spawnLocation + topLeftFarm;
				AddChild(NameName);

			}

			
		}
	}
	public override void _Input(InputEvent @event)
	{
		// Mouse in viewport coordinates.
		if (@event is InputEventMouseButton eventMouseButton){
			if(eventMouseButton.ButtonIndex == MouseButton.Left && eventMouseButton.IsPressed()){
				GD.Print("Mouse Click at: ", eventMouseButton.Position);
				var instantate = ButtonInstantiated.Instantiate();
				((Node2D)instantate).Position = eventMouseButton.Position; 
				AddChild(instantate);

			}
			

		}
	}
}
