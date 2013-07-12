(function() {
  var StatMachine;

  StatMachine = (function() {
    function StatMachine() {
      this.initialize();
    }

    StatMachine.prototype.initialize = function() {
      this.frequency = [];
      this.results = [];
      
      this.average = 0;
      this.max = 0;
      this.mean = 0;
      this.min = 0;
      this.mode = 0;
      this.range = 0;
      this.sum = 0;
    };

    StatMachine.prototype.addNumber = function(number){
      if(existing = _.find(this.frequency, function(obj){ return obj.time == number })){
        existing.count += 1;
      }else{
        this.frequency.push({time: number, count: 1});
      }
      this.results.push(number);
      this.sum += number;
      if(number < this.min){ this.min = number; }
      if(number > this.max){ this.max = number; }
    };

    StatMachine.prototype.summary = function(){
      this.average = this.sum/this.results.length;
      this.range = this.max-this.min;
    
      this.mode =  _.max(this.frequency, function(freq){ return freq.count }).time;
      this.mean = this.results.sort()[Math.round((this.results.length+1)/2)];

      console.log(this.average);
    };

    StatMachine.prototype.reset = function() {
      this.initialize();
    };

    return StatMachine;
  })();

  this.StatMachine = StatMachine;

}).call(this);
