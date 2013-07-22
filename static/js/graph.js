var width = 500;
var height = 500;
var graphpadding = 50;
var graphheight = 400;
var graphwidth = 400;
var svg;
var graphs;
var xScale;
var x = d3.scale.linear()
	.domain([0, 100])
	.range([0, graphwidth]);

var y = d3.scale.linear()
	.domain([0, 100])
	.range([graphheight, 0]);

var line = d3.svg.line()
	.x(function(d){
		return x(d[0]);
	})
	.y(function(d){
		return y(d[1]);
	});

var svg = d3.select("body")
	.append("svg")
	.attr("width", width)
	.attr("height", height);

var make_y_axis = function(){
	return d3.svg.axis()
	.scale(y)
	.orient("left")
	.ticks(10)
};

var make_x_axis = function(){
	return d3.svg.axis()
	.scale(x)
	.orient("bottom")
	.ticks(10)
}

// svg.selectAll("circle")
// 	.data(dataset)
// 	.enter()
// 	.append("circle")
// 	.attr("cx", function(){
// 		return d[graphdataone];
// 	})
// 	.attr("cy", function(){
// 		return d[graphdatatwo];
// 	})
// 	.attr("r", 2);

// svg.append("svg:rect")
// 	.attr("width", width)
// 	.attr("height", height)
// 	.attr("class", "plot");

var xAxis;
var yAxis;
var chartBody;

function setupGraph(){
	svg = d3.select("#graph")
		.append("svg")
		.attr("width", width)
		.attr("height", height)
		.attr("padding", graphpadding);

	xScale = d3.scale.linear()
	.domain([d3.min(graphdata[dataX], function(d){ return d[0] }), d3.max(graphdata[dataX], function(d){ return d[0] })])
	.range([0, graphwidth]);
	// svg.append("svg:rect")
	// 	.attr("width", width)
	// 	.attr("height", height)
	// 	.attr("class", "plot");

	xAxis = d3.svg.axis().scale(xScale).orient("bottom");

	yAxis = d3.svg.axis().scale(y).orient("left");
	svg.append("g")
		.attr("class", "x axis")
		.attr("transform", "translate(50, " + graphheight + ")")
		.call(xAxis);

	svg.append("g")
		.attr("class", "y axis")
		.attr("transform", "translate(50, 0)")
		.call(yAxis);

	svg.append("g")
		.attr("class", "x grid")
		.attr("transform", "translate(50, " + graphheight + ")")
		.call(make_x_axis()
			.tickSize(-graphheight, 0, 0)
			.tickFormat(""));

	svg.append("g")
		.attr("class", "y grid")
		.attr("transform", "translate(50,  0)")
		.call(make_y_axis()
			.tickSize(-graphwidth, 0, 0)
			.tickFormat(""));

	chartBody = svg.append("g")
		.attr("clip-path", "url(#clip)");

}

function graphData(data, index){
	var tobegraphed = new Array();
	for (index in dataY){
		tobegraphed[0] = graphdata[dataX];
		tobegraphed[1] = graphdata[dataY[index]];
		chartBody.append("svg:path")
		.datum(tobegraphed)
		.attr("class", "line graph_"+index)
		.attr("id", index)
		.attr("d", line);
	}
}

	
