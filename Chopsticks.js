



class hand{
    constructor(Fingers, Object){
        this.Object = document.getElementById(Object);
        this.Fingers = Fingers;
        this.Object.innerHTML = String(this.Fingers)
        this.Enabled = true;
    }
    AddFinger(Number){
        this.Fingers += Number;
    }
}
class player{
    constructor(Hand1, Hand2, Initiative, PlayerNumber){
        this.hand1 = new hand(Hand1, "p"+PlayerNumber+"h1");
        this.hand2 = new hand(Hand2, "p"+PlayerNumber+"h2");
        this.Initiative = Initiative;
        this.Selected = this.hand1;
    }
}


function Button(){
    if(p1.Initiative > 0){
        Attack(p1.Selected,p2.Selected)
    }
    else if(p2.Initiative > 0){
        Attack(p2.Selected,p1.Selected)
    }
}
function SwapInitiative(){
    if(p1.Initiative > 0){
        p1.Initiative = 0
        p2.Initiative = 1
    }
    else if(p2.Initiative > 0){
        p1.Initiative = 1
        p2.Initiative = 0
    }
}
/*Takes in the Hand that Took Damage */
function Select(Player, hand){
    
    console.log(hand)
    if(Player == "p1"){
        Player = p1
    }
    else if (Player == "p2"){
        Player = p2
        console.log("p2")
    }
    if(hand == "h1" && Player.hand1.Enabled){
        hand = Player.hand1
        console.log("h1")

    }
    else if (hand == "h2" && Player.hand2.Enabled){
        hand = Player.hand2
        console.log("h2")

    }
    Player.Selected.Object.style.color = "black"
    Player.Selected = hand;
    Player.Selected.Object.style.color = "white"
}

function WriteHand(h2){
    h2.Object.innerHTML = h2.Fingers;
}
function Attack(h1,h2){
    h2.Fingers += h1.Fingers;
    if(h2.Fingers > 4){
        h2.Fingers = 0;
        h2.Enabled = false; 
    }
    WriteHand(h2);
    SwapInitiative();
}


var p1 = new player(1,1,1,"1");
var p2 = new player(1,1,1,"2");

var Turn = p1;



