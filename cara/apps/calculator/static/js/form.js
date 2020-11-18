/* -------HTML structure------- */
function getChildElement(elem) {
  // Get the element named in the given element's data-enables attribute.
  return $("#" + elem.data("enables"));
}

function insertSpanAfter(referenceNode, text) {
  var element = document.createElement("span");
  element.classList.add("red_text");
  element.innerHTML = "&nbsp;&nbsp;" + text; 
  referenceNode.parentNode.insertBefore(element, referenceNode.nextSibling);
}

/* -------Required fields------- */
function require_fields(obj) {
  switch ($(obj).attr('id')) {
    case "room_type_volume":
      require_room_volume(true);
      require_room_dimensions(false);
      break;
    case "room_type_dimensions":
      require_room_volume(false);
      require_room_dimensions(true);
      break;
    case "mechanical":
      require_mechanical_ventilation(true);
      require_natural_ventilation(false);
      break;
    case "natural":
      require_mechanical_ventilation(false);
      require_natural_ventilation(true);
      break;
    case "air_type_changes":
      require_air_changes(true);
      require_air_supply(false);
      break;
    case "air_type_supply":
      require_air_changes(false);
      require_air_supply(true);
      break;
    case "event_type_single":
      require_single_event(true);
      require_recurrent_event(false);
      break;
    case "event_type_recurrent":
      require_recurrent_event(true);
      require_single_event(false);
      break;
    case "lunch_option_no":
      require_lunch(false);
      break;
    case "lunch_option_yes":
      require_lunch(true);
      break;
    case "mask_on":
      require_mask(true);
      break;
    case "mask_off":
      require_mask(false);
      break;
    case "hepa_yes":
      require_hepa(true);
      break;
    case "hepa_no":
      require_hepa(false);
      break;
    default:
      break;
  }
}

function unrequire_fields(obj) {
  switch (obj.id) {
    case "mechanical":
      require_mechanical_ventilation(false);
      break;
    case "natural":
      require_natural_ventilation(false);
      break;
    default:
      break;
  }
}

function require_room_volume(option) {
  require_input_field("#room_volume", option);
}

function require_room_dimensions(option) {
  require_input_field("#floor_area", option);
  require_input_field("#ceiling_height", option);
}

function require_mechanical_ventilation(option) {
  $("#air_type_changes").prop('required', option);
  $("#air_type_supply").prop('required', option);
  if (!option) {
    removeInvalid("#air_changes");
    removeInvalid("#air_supply");
  }
}

function require_natural_ventilation(option) {
  require_input_field("#windows_number", option);
  require_input_field("#window_height", option);
  require_input_field("#opening_distance", option);
  $("#always").prop('required', option);
  $("#interval").prop('required', option);
}

function require_air_changes(option) {
  require_input_field("#air_changes", option);
}

function require_air_supply(option) {
  require_input_field("#air_supply", option);
}

function require_single_event(option) {
  require_input_field("#single_event_date", option);
}

function require_input_field(id, option) {
  $(id).prop('required', option);
  if (!option)
    removeInvalid(id);
}

function require_recurrent_event(option) {
  $("#recurrent_event_month").prop('required', option);
}

function require_lunch(option) {
  $("#lunch_start").prop('required', option);
  $("#lunch_finish").prop('required', option);
  if (option) {
    var start = document.getElementById("lunch_start");
    if (start.value === "")
      start.value = "12:30";
    var finish = document.getElementById("lunch_finish");
    if (finish.value === "")
      finish.value = "13:30";
  } 
  else {
    document.getElementById("lunch_start").value = "";
    document.getElementById("lunch_finish").value = "";
    $("#lunch_finish").removeClass("red_border");
    $("#lunch_time_error").hide();
  }
}

function require_mask(option) {
  $("#mask_type1").prop('required', option);
  $("#mask_ffp2").prop('required', option);
}

function require_hepa(option) {
  require_input_field("#hepa_amount", option);
}

function setMaxInfectedPeople() {
  $("#training_limit_error").hide();
  var max = $("#total_people").val()

  if ($("#activity_type").val() === "training") {
    max = 1;
    $("#training_limit_error").show();
  }

  $("#infected_people").attr("max", max);
}

function removeInvalid(id) {
  if ($(id).hasClass("red_border")) {
    $(id).val("");
    $(id).removeClass("red_border");
    $(id).next('span').remove();
  }
}

function on_ventilation_type_change() {
  ventilation_types = $('input[type=radio][name=ventilation_type]');
  ventilation_types.each(function (index) {
    if (this.checked) {
      getChildElement($(this)).show();
      require_fields(this);
    } else {
      getChildElement($(this)).hide();
      unrequire_fields(this);
      // Clear the inputs for this newly hidden child element.
      getChildElement($(this)).find('input').not('input[type=radio]').val('');
      getChildElement($(this)).find('input[type=radio]').prop("checked", false);
      getChildElement($(this)).find('input').prop("required", false);
    }
  });
}

/* -------UI------- */
$(function () {
  $(".datepicker").datepicker({
    dateFormat: 'dd/mm/yy'
  });
});

function show_disclaimer() {
  var dots = document.getElementById("dots");
  var moreText = document.getElementById("more");
  var btnText = document.getElementById("myBtn");

  if (dots.style.display === "none") {
    dots.style.display = "inline";
    btnText.innerHTML = "Read more";
    moreText.style.display = "none";
  } else {
    dots.style.display = "none";
    btnText.innerHTML = "Read less";
    moreText.style.display = "inline";
  }
}

function check_radio(id) {
  $(id).click();
}

/* -------Form validation------- */
function validate_form(form) {
  var submit = true;

  //Validate all non zero values
  $("input[required].non_zero").each(function() {
    if (!validateValue(this))
      submit = false;
  });

  //Validate all dates
  $("input[required].datepicker").each(function() {
    if (!validateDate(this))
      submit = false;
  });

  //Validate all times
  $("input[required].finish_time").each(function() {
    if (!validateFinishTime(this))
      submit = false;
  });

  return submit;
}

function validateValue(obj) {
  $(obj).removeClass("red_border");
  $(obj).next('span').remove();

  if (!isNonZeroOrEmpty($(obj).val())) {
    $(obj).addClass("red_border");
    insertSpanAfter(obj, "Value must be > 0");
    return false;
  }
  return true;
}

function isNonZeroOrEmpty(value) {
  if (value === "") return true;
  if (value == 0) 
    return false;
  return true;
}

function validateDate(obj) {
  $(obj).removeClass("red_border");
  $(obj).next('span').remove();

  if (!isValidDateOrEmpty($(obj).val())) {
    $(obj).addClass("red_border");
    insertSpanAfter(obj, "Incorrect date format");
    return false;
  }
  return true;
}

function isValidDateOrEmpty(date) {
  if (date === "") return true;
  var matches = /^(\d+)[-\/](\d+)[-\/](\d+)$/.exec(date);
  if (matches == null) return false;
  var d = matches[1];
  var m = matches[2];
  var y = matches[3];
  if (y > 2100 || y < 1900) return false;
  var composedDate = new Date(y + '/' + m + '/' + d);
  return composedDate.getDate() == d && composedDate.getMonth() + 1 == m && composedDate.getFullYear() == y;
}

function validateFinishTime(obj) {
  $(obj).removeClass("red_border");
  $(obj).next('span').remove();

  var startTime = parseValToNumber($(obj).prev().val());
  var finishTime = parseValToNumber(obj.value);
  if (startTime > finishTime) {
    $(obj).addClass("red_border");
    insertSpanAfter(obj, "Finish time must be after start");
    return false;
  }
  return true;
}

function parseValToNumber(val) {
  return parseInt(val.replace(':',''), 10);
}

/* -------On Load------- */
$(document).ready(function () {
  // When the document is ready, deal with the fact that we may be here
  // as a result of a forward/back browser action. If that is the case, update
  // the visibility of some of our inputs.

  // When the ventilation_type changes we want to make its respective
  // children show/hide.
  $("input[type=radio][name=ventilation_type]").change(on_ventilation_type_change);
  // Call the function now to handle forward/back button presses in the browser.
  on_ventilation_type_change();

  //Same for lunch option
  require_fields($("input[name='lunch_option']:checked"));

  // Setup the maximum number of people at page load (to handle back/forward),
  // and update it when total people is changed.
  setMaxInfectedPeople();
  $("#total_people").change(setMaxInfectedPeople);
  $("#activity_type").change(setMaxInfectedPeople);

  //Validate all non zero values
  $("input[required].non_zero").each(function() {validateValue(this)});
  $(".non_zero").change(function() {validateValue(this)});

  //Validate all dates
  $("input[required].datepicker").each(function() {validateDate(this)});
  $(".datepicker").change(function() {validateDate(this)});

  //Validate all finish times
  $("input[required].finish_time").each(function() {validateFinishTime(this)});
  $(".finish_time").change(function() {validateFinishTime(this)});
  $(".start_time").change(function() {validateFinishTime(this.nextSibling.nextSibling)});

  var radioValue = $("input[name='event_type']:checked");
  if (radioValue.val()) {
    require_fields(radioValue.get(0));
  }
});

/* -------Debugging------- */
function debug_submit(form) {

  //Prevent default posting of form - put here to work in case of errors
  event.preventDefault();

  //Serialize the data in the form
  var serializedData = objectifyForm($(form).serializeArray());

  console.log(serializedData);

  return false; //don't submit
}

function objectifyForm(formArray) {
  var returnArray = {};
  for (var i = 0; i < formArray.length; i++)
    returnArray[formArray[i]['name']] = formArray[i]['value'];
  return returnArray;
}