(function($) {

     /*
      * For form inputs: disable form submission on 'enter' key
      */
     $.fn.preventEnterKey = function() {
         return $(this).on('keypress', function(e) {                              
                            if (e.keyCode == 13) {
                                e.preventDefault();
                            }
                        });
     };

     // live search initialization
     function initLiveSearch() {
         var datasets = [
             { name: 'documents',
               remote: '/search/live?type=documents&q=%QUERY',
               limit: 15,
               engine: Hogan,
               header: '<b><i>Documents</i></b>',
               template: '<img src="{{icon}}" width="16" height="16" /> {{value}}'
             }
         ];

         if (Abilian.current_user.crm) {
             datasets.push({ name: 'partenaires',
                             remote: '/search/live?type=partenaires&q=%QUERY',
                             limit: 15,
                             engine: Hogan,
                             header: '<b><i>Partenaires</i></b>',
                             template: '{{value}}'
                           });
             datasets.push({ name: 'contacts',
                             remote: '/search/live?type=contacts&q=%QUERY',
                             limit: 15,
                             engine: Hogan,
                             header: '<b><i>Contacts</i></b>',
                             template: '{{#photo}}<img src="{{photo}}" width="16" height="16" /> {{/photo}}{{value}}'
                           });
             datasets.push({ name: 'projets',
                             remote: '/search/live?type=projets&q=%QUERY',
                             limit: 15,
                             engine: Hogan,
                             header: '<b><i>Projets</i></b>',
                             template: '{{value}}'
                           });
             /*      datasets.push({ name: 'visites',
                                     remote: '/search/live?type=visites&q=%QUERY',
                                     limit: 15,
                                     engine: Hogan,
                                     header: '<b><i>Visites</i></b>',
                                     template: '{{value}}'
              });
              datasets.push({ name: 'actionfilieres',
                      remote: '/search/live?type=actionfilieres&q=%QUERY',
                      limit: 15,
                      engine: Hogan,
                      header: '<b><i>Actions Filières</i></b>',
                      template: '{{value}}'
              });
              */
         }

         var search_box = $("#search-box");
         search_box.typeahead(datasets)
             .on('typeahead:selected', function (e, data) {
                     if (data.url) {
                         e.preventDefault();
                         document.location = data.url;
                     }
                 });

         // on enter key: go to search page
         var typeahead = search_box.data('ttView');
         typeahead.inputView.on(
             'enterKeyed',
             function(e) { search_box.get(0).form.submit(); }
         );
     }

     function datetimePickerSetup() {
         /*
          * automatically concat datepicker + timepicker in hidden input
          */
         $('.datetimepicker').each(
             function() {
                 var $self = $(this);
                 var $datepicker = $('#'+ this.id + '-date');
                 var $timepicker = $('#'+ this.id + '-time');
                 
                 $datepicker.parent().on(
                     'changeDate',
                     function updateDateTime(e) {
                         $self.val($datepicker.val() + ' ' + $timepicker.val());
                     }
                 );

                 $timepicker.timepicker().on(
                     'changeTime.timepicker',
                     function updateDateTime(e) {
                         $self.val($datepicker.val() + ' ' + e.time.value);
                     }
                 );
             }
         );


     }

     function appInit() {
         initLiveSearch();

         $('button').tooltip({delay: 500});
         $('a.btn').tooltip({delay: 500});

         $('.dropdown-toggle').dropdown();

         $('.tagbox').tagBox();

         $('.dynamic-row-widget').dynamicRowWidget();

         $('.js-widget').each(Abilian.init_js_widget);

         $(".datepicker").datepicker({weekStart: 1, format: 'dd/mm/yyyy'});
         $(".timepicker").timepicker()
            .on('click.timepicker',
                function(e) {
                    e.preventDefault();
                    $(this).timepicker('showWidget');
                }
               );
         datetimePickerSetup();

         $(".select2").select2({width: "220px", placeholder: "", allowClear: true});

         // Use a POST instead of a GET to log out.
         $("a#logout").on(
             'click',
             function() {
                 var form = $('<form></form>');
                 form.attr("method", "post");
                 form.attr("action", "/login/logout");
                 $(document.body).append(form);
                 form.submit();
             });

         $(document).trigger(Abilian.events.widgetsInitialized);

         /* uses moment.js */
         $('.time').each(function(i, e) {
           var time = moment.unix($(e).attr('data-timestamp'));
           $(e).html('<span>' + time.fromNow() + '</span>');
         });

     }

     $(document).ready(appInit);
}(jQuery));

/*
 * Fancy file upload. Doesn't work well enough yet.
 */

/*
 $(function() {
 $('#fileupload').fileupload({
 dataType: 'json',

 done: function(e, data) {
 $.each(data.result, function(index, file) {
 $('<p/>').text(file.name).appendTo(document.body);
 });
 },

 add: function(e, data) {
 $.each(data.result, function(index, file) {
 $('<p/>').text(file.name).appendTo(document.body);
 });
 }
 });
 });

 */

/* ==========================================================
 * bootstrap-placeholder.js v2.0.0
 * http://jasny.github.com/bootstrap/javascript.html#placeholder
 *
 * Based on work by Daniel Stocks (http://webcloud.se)
 * ==========================================================
 * Copyright 2012 Jasny BV.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ========================================================== */

/* TODO: turn this into a proper bootstrap plugin */
$(function() {
  $('*[data-fileupload]').each(function() {
    var container = $(this);
    var input = $(this).find(':file');
    var name = input.attr('name');
    if (input.length == 0) return;

    var preview = $(this).find('.fileupload-preview');
    if (preview.css('display') != 'inline' && preview.css('height') != 'none') {
      preview.css('line-height', preview.css('height'));
    }

    var remove = $(this).find('*[data-dismiss="fileupload"]');

    var hidden_input = $(this).find(':hidden[name="' + name + '"]');
    if (!hidden_input.length) {
      hidden_input = $('<input type="hidden" />');
      container.prepend(hidden_input);
    }

    var type = container.attr('data-fileupload') == "image" ? "image" : "file";

    input.change(function(e) {
      hidden_input.val('');
      hidden_input.attr('name', '');
      input.attr('name', name);

      var file = e.target.files[0];

      if (type == "image" && preview.length
          && (typeof file.type !== "undefined" ? file.type.match('image.*') : file.name.match('\\.(gif|png|jpg)$'))
          && typeof FileReader !== "undefined") {
        var reader = new FileReader();

        reader.onload = function(e) {
          preview.html('<img src="' + e.target.result + '" ' + (preview.css('max-height') != 'none' ? 'style="max-height: ' + preview.css('max-height') + ';"' : '') + ' />');
          container.addClass('fileupload-exists').removeClass('fileupload-new');
        };

        reader.readAsDataURL(file);
      } else {
        preview.html(escape(file.name));
        container.addClass('fileupload-exists').removeClass('fileupload-new');
      }
    });

    remove.click(function() {
      hidden_input.val('');
      hidden_input.attr('name', name);
      input.attr('name', '');

      preview.html('');
      container.addClass('fileupload-new').removeClass('fileupload-exists');

      return false;
    });
  });
});
