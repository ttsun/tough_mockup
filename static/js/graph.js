margin = {
	top: 20, 
	right: 50, 
	bottom: 50,
	left: 80, 
}
var width = 500;
var height = 500;
var graphpadding = 50;
var graphheight = 400;
var graphwidth = 400;
var svg;
var graphs;
var xScale;
var dataYindex = 0;
var yScale = d3.scale.linear()
	.domain([0, 100])
	.range([graphheight, 0]);

var line = d3.svg.line()
	.x(function(d){
		return xScale(d[dataX]);
	})
	.y(function(d){
		return yScale(d[dataY[dataYindex]]);
	});

var svg = d3.select("body")
	.append("svg")
	.attr("width", width)
	.attr("height", height);

var make_y_axis = function(){
	return d3.svg.axis()
	.scale(yScale)
	.orient("left")
	.ticks(10)
};

var make_x_axis = function(){
	return d3.svg.axis()
	.scale(xScale)
	.orient("bottom")
	.ticks(10)
}

var xAxis;
var yAxis;
var plot;
var clip;
var chartBody;

function setupGraph(){
	svg = d3.select("#graph")
		.append("svg")
		.attr("width", width)
		.attr("height", height)
		.attr("padding", graphpadding);

	xScale = d3.scale.linear()
	.domain([d3.min(graphdata, function(d){
		return d[dataX];
	}), d3.max(graphdata, function(d){
		return d[dataX];
	})])
	.range([0, graphwidth]);

	xAxis = d3.svg.axis().scale(xScale).orient("bottom");

	yAxis = d3.svg.axis().scale(yScale).orient("left");

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

	var xlabelheight = 450;
	svg.append("text")
		.attr("class", "labels")
		.attr("transform", "translate("+graphwidth/2+", "+xlabelheight+")")
		.text(dataXname);

	// svg.append("text")
	// 	.attr("class", "labels")
	// 	.attr("transform", "rotate(-90) translate(-"+graphheight/2+", 15)")
	// 	.text(dataXname);

	plot = svg.append("svg:rect")
		.attr("width", graphwidth)
		.attr("height", graphheight)
		.attr("class", "plot")
		.attr("transform", "translate(50, 0)");

	clip = svg.append("svg:clipPath")
				.attr("id", "clip")
				.append("svg:rect")
				.attr("x", 0)
				.attr("y", 0)
				.attr("width", graphwidth)
				.attr("height", graphheight)
				.attr("transform", "translate(50, 0)");

	chartBody = svg.append("g")
		.attr("clip-path", "url(#clip)");

}

function graphData(){
	// console.log(tobegraphed);
	while (dataYindex < dataY.length){
		chartBody.append("svg:path")
		.datum(graphdata)
		.attr("class", "line graph_"+dataY[dataYindex])
		.attr("transform", "translate(50, 0)")
		.attr("d", line)
		.attr("stroke", colorsY[dataYindex])
		.attr("fill", 'None')
		dataYindex++;
	}
	dataYindex = 0;
}

function rescaleY(){
	if(dataY.length > 0){
		var minsArray = new Array();
		for (index in dataY){
			minsArray.push(d3.min(graphdata, function(d){
				return d[dataY[index]];
			}));
		}
		console.log(minsArray);
		minY = d3.min(minsArray);
		console.log(minY);

		var maxArray = new Array();
		for (index in dataY){
			maxArray.push(d3.max(graphdata, function(d){
				return d[dataY[index]];
			}));
		}
		console.log(maxArray);
		maxY = d3.max(maxArray);
		console.log(maxY);

		yScale = d3.scale.linear()
		.domain([minY, maxY])
		.range([graphheight, 0]);
	}else{
		yScale = d3.scale.linear()
		.domain([0, 100])
		.range([graphheight, 0]);
	}

	yAxis = d3.svg.axis().scale(yScale).orient("left");

	svg.select(".y.axis").call(yAxis);

	svg.select(".y.grid")
		.call(make_y_axis()
			.tickSize(-graphheight, 0, 0)
			.tickFormat(""));
}

function rescaleX(){
	var minX = d3.min(graphdata, function(d){
		return d[dataX];
	});
	var maxX = d3.max(graphdata, function(d){
		return d[dataX];
	});

	xScale = d3.scale.linear()
		.domain([minX, maxX])
		.range([0, graphwidth]);

	svg.select(".x.axis").call(xAxis);

}
	
