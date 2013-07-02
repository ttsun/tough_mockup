function init_block(blockType){
	if(warn_unsaved_changes() == true) return;

	setup_div(blockType);	
	showHideBlockHelp(blockType);
}

function showHideBlockHelp(blockType){
	var theTextField = document.getElementById('thetext');
	var helpText = 'Copy and paste a position file in ' + blockType + ' format.';
	if (theTextField.value == '' && current_doc == blockType) {
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

function save_block_text(blockType){
	$('#save-loader').show();
	//central function for saving poscar settings from the text form
	var content = document.getElementById('thetext').value;
	// var validation_errors = validate_poscar(content);
	// if (validation_errors && !confirm("Warning: " + validation_errors + "\nSave anyway?")) {
	// 	$('#save-loader').hide();
	// 	return;
	// }
	//save the text as a file on the server and update the jobfiles object
	save_form(content);
	return false;
}