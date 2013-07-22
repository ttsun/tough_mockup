var width;
var height;
var x = d3.scale.linear()
	.domain([0, 100])
	.range([0, width]);
var y = d3.scale.linear()
	.domain([0, 100])
	.range([height, 0]);
var line = d3.svg.line()
	.x(function(d){
		return x(d.time);
	})
	.y(function(d){
		return y(d.value);
	});

svg.append("svg:rect")
	.attr("width", width)
	.attr("height", height)
	.attr("class", "plot");

var xAxis = d3.svg.axis().scale(x).orient("bottom");

var yAxis = d3.svg.axis().scale(y).orient("left");

svg.append("svg:g")
	.attr("class", "x axis")
	.attr("transform", "translate(0, " + height + ")")
	.call(xAxis);

svg.append("g")
	.attr("class", "y axis")
	.call(yAxis);

svg.append("g")
	.attr("class", "x grid")
	.attr("transform", "translate(0, " + height + ")")
	.call(make_x_axis()
		.tickSize(-height, 0, 0)
		.tickFormat(""));

svg.append("g")
	.attr("class", "y grid")
	.call(make_y_axis()
		.tickSize(-width, 0, 0)
		.tickFormat(""));

var chartBody = svg.append("g")
	.attr("clip-path", "url(#clip)");

function graphData(data){
	if(clearData){
		chartBody.selectAll(".line").remove();
	}
	chartBody.append("svg:path")
	.datum(data)
	.attr("class", "line")
	.attr("d", line);
	refresh();
}
	
