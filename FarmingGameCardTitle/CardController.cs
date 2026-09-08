using Godot;
using System;

public partial class CardController : Node
{
	// Called when the node enters the scene tree for the first time.
	public Json jsonHolder;
	public String jsonPath = "farmingTypes.json";
	
	public override void _Ready()
	{
		//Open File of jsonPath
		FileAccess temp = FileAccess.Open(jsonPath, FileAccess.ModeFlags.Read);
		//read it as a string. 
		String temp3 = temp.GetAsText();
		//Parse the string (Thats in JSon form) Temp 2 stores the good good of the JSON file. 
		Variant temp2 = Json.ParseString(temp3);
	
	}

	// Called every frame. 'delta' is the elapsed time since the previous frame.
	public override void _Process(double delta)
	{
	}
}
