function onLoad() {
	$("input[name='name']").val($.cookie('name'));
}

function onSubmit() {
	$.cookie('name', $("input[name='name']").val());
	
	// check required fields
	//return checkForm()
}

function clearForm() {
	$("input[name='title']").val("")
	$("textarea[name='content']").val("")
}
