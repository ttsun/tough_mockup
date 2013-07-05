/**
 * @author agreiner
 */
var current_doc = '';
var csrftoken = getCookie('csrftoken');

function init_input(file_id){
	if(warn_unsaved_changes() == true) return;
	//test whether a div for gui input exists. If so, use that initially. otherwise use the default text input
	if(document.getElementById(file_id + "-gui") !== null) var div_type = 'gui';
	else var div_type = 'text';
	setup_div(file_id + '-' + div_type);
	showHideHelp(file_id);//need to make general version of help
}
function showHideHelp(file_id){
	var theTextField = document.getElementById('thetext');
	var helpText = 'Copy and paste a file in ' + file_id + ' format.';
	if (theTextField.value == '' && current_doc == file_id) {
		theTextField.value = helpText;
		theTextField.style.color = "#666";
	}
	$('#thetext').focus(function(){
		if (theTextField.value == helpText) {
			theTextField.value = '';
			theTextField.style.color = "#000";
		}
	});
}


//indicate when an edit has been made in any input element
//takes care of most cases, but see potcar.js
$(':input').change(function() {
	note_change();
});
$('#thetext').keypress(function(){
	note_change();
});
function note_change(){
	//indicate that an edit has been made
	//show the asterisks
	$('#gui-text-buttons').addClass('changed');	
}
function form_was_changed(){
	//tell whether a change has been made to the current form since last save
	if($('#gui-text-buttons').hasClass('changed')) return true;
}



function show_buttons(div){
	var content, theP;
	switch (div){
		
		 /*
		  * example GUI option with a tab for raw text input and a tab for graphical editing
		  * 
		  * 
		 case 'kpoints-gui':
			content = '<p><span class="active">Graphical</span> <span class="inactive"><a href="" onclick="kpoints_gui_to_text();return false;">Raw Text</a></span></p>';
			break;
		*/
		case 'default':
			content = '';
			break;
		case 'batch-gui':
			content = '';
			break;
		default:
			content = '<p><span class="active">Raw Text</></span></p>';
	}
	theP = document.getElementById('gui-text-buttons');
	theP.className = theP.className.replace(/\bhidden\b/, '');
	theP.innerHTML = content;
}



function warn_unsaved_changes(){
	//alert the user if they are abandoning unsaved changes.
	if(!form_was_changed()) return false;
 	
 	if(!confirm("Are you sure you want to navigate away from this form? Your changes have not been saved.")) return true;
}

function cancel_form(){
	if(warn_unsaved_changes() != true) setup_div('default');		
}

function save_form(file_content){
	console.log(current_doc);
	file_name = current_doc=='batch'? 'tough.pbs': current_doc;

	//remove \r so IE doesn't mess up
	var post_data = {filename: file_name, content: file_content.replace(/\r/g, '')};
	jobfiles[current_doc] = post_data.content;

	$.ajax({
		type: 'POST',
		url: TOUGH_SUBDIR + '/save/' + jobid,
		data: post_data,
		success: function(data){
		    if ($('#login_form', data).size() > 0) {
				location.reload();
			}
			Alertify.log.success(file_name + " successfully saved");
			if (data) {
				//do nothing
			}
			$('#save-loader').hide();
		},
		error: function(err){
			alert("Error Saving Form");
			$('#save-loader').hide();
		}
	});
	return false;
}

function save_text_form(file_content){
	$('#save-loader').show();
	save_form(file_content);
	
}

function init_batch(){
	if(warn_unsaved_changes() == true) return;
	setup_div('batch-gui');	
	guify_batch();
	$('#batch_form').validate({
		onSubmit: false,
		errorElement:"p",
		//most validations are specified with a class on the form input, but these are too complex for that
		rules:{
			numnodes:{
				required: true,
				digits: true,
				max: 400
			}
			// ppn:{
			// 	required: true,
			// 	digits: true,
			// 	max: 8
			// },
			// pvmem:{
			// 	digits: true,
			// }
		},		
		debug: true
	});
}

function textify_batch(){
	//changing to fit Hopper
	var content = '';
	content += '#PBS -N tough\n';
	content += '#PBS -q ' + document.getElementById('id_queue').value + '\n';
	content += '#PBS -l mppwidth=' + document.getElementById('id_numnodes').value * 24 
	
	var numprocs= parseInt(document.getElementById('id_numnodes').value) * 24

	var nodemem = document.getElementById('id_nodemem').value;
	
	if(nodemem!='first') {
	    content += ':' + nodemem + '\n';
	} else {
	    content += '\n';
 	}
	if (($('#id_wallhours').val()!="") && ($('#id_wallminutes').val()!="")) {
	    content += '#PBS -l walltime=' + document.getElementById('id_wallhours').value + ':' + document.getElementById('id_wallminutes').value + ':00\n';
	}
	//define directories that can be used in gres line of batch script. Format is 'directory': 'appropriate_gres_option_for_that_directory'
	var gres_options={'/project': 'project', '/global/project': 'project', '/global/scratch': 'gscratch', '/projectb': 'projectb', '/global/projectb': 'projectb'};
	var gres_string = '';
	for (dir in gres_options){
		var dir_esc = dir.replace(/\//g, '\\\/');
		var gres_pattern = new RegExp('^'+ dir_esc + '\/.+');
		if ($('#jobdir').val().search(gres_pattern) != -1) gres_string = gres_options[dir];
	}
	if(gres_string != '') content += '#PBS -l gres=' + gres_string + '\n';
	content += '#PBS -m '
	var mail = '';
	if(document.getElementById('id_notifications_begin').checked) mail += 'b';
	if(document.getElementById('id_notifications_end').checked) mail += 'e';
	if(document.getElementById('id_notifications_abort').checked) mail += 'a';
	if(!mail) mail = 'n';
	content += mail + '\n';
	var repo = document.getElementById('id_repo').value;
	if (repo && (repo!="default")) { 
	    content += '#PBS -A ' + repo + '\n';
	}
	content += '#PBS -j oe\n';
	content += '#PBS -d ' + document.getElementById('jobdir').value + '\n';
	content += '#PBS -V\n\n';
	content += 'cd ' + document.getElementById('jobdir').value + '\n';
	content += 'module load tough/noah\n\n' 
	// + version + '\n\n';
	content += "/bin/date -u  +'%a %b %d %H:%M:%S %Z %Y' > started\n"
	content += 'aprun -n ' + numprocs.toString() + ' ' + "tough"+ '\n';
	content += "/bin/date -u  +'%a %b %d %H:%M:%S %Z %Y' > completed\n";
	return content;
}

function guify_batch(){
	//read the batch file and update the gui controls to show selections
	//changing to fit Hopper
	var batchFile = jobfiles['batch'];
	//start from default form settings
	document.forms['batch_form'].reset();
	var lines = batchFile.split('\n');
	if(lines[0] == '#PBS -N tough'){
		//this is a nova-generated file
		for (i in lines) {
			var line = lines[i];
			//deal with PBS directives
			var theMatch = line.match(/^#PBS -(\w) (.*)?/);
			if (theMatch) {
				var option = theMatch[1];
				var args = theMatch[2];
				switch (option) {
					case 'q':
						document.getElementById('id_queue').value = args;
						break;
					case 'l':
						var nodedist = args.match(/mppwidth=(\d+)/);
							// :ppn=(\d+):?(\w+)?/);
						if (nodedist) {
							document.getElementById('id_numnodes').removeAttribute("placeholder");
							document.getElementById('id_numnodes').value = nodedist[1]/24;
							// document.getElementById('id_ppn').value = nodedist[2];
							// if(nodedist[3]) document.getElementById('id_nodemem').value = nodedist[3];
							break;
						}
						var memory = args.match(/pvmem=(\d+)/);
						if (memory) {
							document.getElementById('id_pvmem').value = memory[1];
							break;
						}
						var wtime = args.match(/walltime=(\d+):(\d+):(\d+)/);
						if (wtime) {
							document.getElementById('id_wallhours').value = wtime[1];
							document.getElementById('id_wallminutes').value = wtime[2];
							break;
						}
						break;
					case 'm':
						if (args.match(/b/)) document.getElementById('id_notifications_begin').checked = true;
						if(args.match(/e/)) document.getElementById('id_notifications_end').checked = true;
						if(args.match(/a/)) document.getElementById('id_notifications_abort').checked = true;
						break;
					case 'd':
						//document.getElementById('jobdir').value = args; //don't do this; use what django sends in the form.
						break;
					case 'A':
						document.getElementById('id_repo').value = args;
						break;
					default:
						//ignore lines that don't match anything
				}
			}
			//deal with other lines of the batch file that don't start with #PBS
			else 
				if (line.slice(0, 11) == 'module load') {
					var module = line.match(/module load tough\/([\d\.]+)/)
					if(module) document.getElementById('id_tough_version').value = module[1];
				}
			else if(line.slice(0,6) == 'aprun'){
				var aprun = line.match(/aprun -n \d+ (\w+)$/);
				if(module) document.getElementById('id_tough_executable').value = aprun[1];
			}
		}
		//update the total number of nodes
		//changed to fit Hopper
		// parseInt(document.getElementById('id_ppn').value);
	}
	else if(lines != ''){
		//this is a non-nova-generated file
		alert("NOVA was not able to parse the current batch file. Please re-enter your computational settings.");
	}
}

function save_batch(){
    
    // Be a little more lenient with missing hours/minutes
    if (($('#id_wallminutes').val()=="") && ($('#id_wallhours').val()!="")) {
        $('#id_wallminutes').val("0");
    }
    
    if (($('#id_wallhours').val()=="") && ($('#id_wallminutes').val()!="")) {
        $('#id_wallhours').val("0");
    }

	// if(!$('#batch_form').isValid()) return;
	$('#save-loader').show();
	//central function for saving batch settings from the GUI
	var content = textify_batch();
	//save the text as a file on the server and update the jobfiles object
	save_form(content);
}

function validate_all(){
	var errors = "";
	var warnings = "";
	
	if (!jobfiles['RAWTOUGH']) {
		errors += "Raw tough file is missing. ";
	}
	var validation = { 'errors': errors, 'warnings': warnings };
	return validation;
}

function is_valid_for_type(value, type){
	switch (type) {
		case 'bool':
			if(value == '.FALSE.' || value == '.TRUE.' || value == '.T.' || value == '.F.' || 'T' || 'F') return true;
			break;
		case 'real':
			if(value.match(/^[-\deE\.]+$/)) return true;
			break;
		case 'realarray':
			if(value.match(/^[-\deE\*\.]+(\s[-\deE\*\.]+)*$/)) return true;
			break;
		case 'int':
			if(value.match(/^-?\d+(\.0+)?$/)) return true;
			break;
		case 'intarray':
			if(value.match(/^-?\d+(\s-?\d+)*$/)) return true;
			break;
		case 'word':
			if(value.match(/^[a-zA-Z0-9_\.]+$/)) return true;
			break;
		case 'string':
			if(value.length > 0) return true;
			break;
		case '3coords':
			if(value.match(/^[-\deE\.]+\s[-\deE\.]+\s[-\deE\.]+$/)) return true;
			break;
		default:
			return false;
	}
}

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}
function sameOrigin(url) {
    // test that a given url is a same-origin URL
    // url could be relative or scheme relative or absolute
    var host = document.location.host; // host + port
    var protocol = document.location.protocol;
    var sr_origin = '//' + host;
    var origin = protocol + sr_origin;
    // Allow absolute or scheme relative URLs to same origin
    return (url == origin || url.slice(0, origin.length + 1) == origin + '/') ||
        (url == sr_origin || url.slice(0, sr_origin.length + 1) == sr_origin + '/') ||
        // or any other URL that isn't scheme relative or absolute i.e relative.
        !(/^(\/\/|http:|https:).*/.test(url));
}

$.ajaxSetup({
    crossDomain: false, // obviates need for sameOrigin test
    beforeSend: function(xhr, settings) {
        if (!csrfSafeMethod(settings.type)) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
    }
});
