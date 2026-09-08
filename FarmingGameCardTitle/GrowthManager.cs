using Godot;
using System;
using System.Net;

public partial class GrowthManager : Node
{
	// Called when the node enters the scene tree for the first time.

	public main mainScene;
	public CardController Cards;
	public Json mainInfo;
	public String staus;
	public override void _Ready()
	{
		staus = "Neutral";
		mainScene = GetNode<main>("../..");
		mainInfo = Cards.jsonHolder;

	}

	// Called every frame. 'delta' is the elapsed time since the previous frame.
	public override void _Process(double delta)
	{
	}
	public void OnButtonButtonDown(){

		if(staus == "Neutral"){

			// Change animation

			String currentCard = "Growing_Peppers";
			ChangeAnimation(currentCard);
			//Update current status.
			staus = "Growing";

			Timer timer = GetNode<Timer>("./GrowthTimer");
			timer.Start();		
		}
		else if(staus == "Growing"){
			GD.Print("WAIT");
		}
		else if(staus == "Grown"){
			String reset = "Neutral";
			ChangeAnimation(reset);
			staus = "Neutral";
			increaseScore();

		}
		

	}
	
	public void ChangeAnimation(String newSprite){
		//Gather node
			GD.Print("ChangeAnimation");

		AnimatedSprite2D sprite = GetNode<AnimatedSprite2D>("../CollisionShape2D2/GrassSprite");
		//play corresponding animation
		sprite.Play(newSprite);

	}
	public void OnGrowthTimerTimeout(){
		String finalCrop = "Grown";

		Timer timer = GetNode<Timer>("./GrowthTimer");
		timer.Stop();
		staus = "Grown";


		ChangeAnimation(finalCrop);
	}
	public void increaseScore(){
		Label label = GetNode<Label>("../../HUD/Score");
		GD.Print(label);
		int score = mainScene.score;
		score += 1;
		label.Text = score.ToString();
		mainScene.score = score;


	}

}
