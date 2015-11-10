(function(factory) {
    'use strict';
    define('SBEFolderListingSetup',
           ['Abilian', 'jquery', 'jquery.dataTables', 'bootbox'],
           factory);
}
 (function(Abilian, $, jqDT, bootbox) {
     'use strict';

     function setupFolderListing() {
         $.fn.dataTableExt.afnFiltering.push(
             function(oSettings, aData, iDataIndex) {
                 var filter_value = $("#filter").val();
                 var row_text = aData[2].trim();
                 return row_text.match(new RegExp(filter_value, "i"));
             }
         );

         var config = document.getElementById('objects-table')
                 .parentElement
                 .nextElementSibling;
         config = JSON.parse(config.textContent);

         var dtParams = {
             aoColumns: [
                 { asSorting: [], sWidth: '1%' },
                 { bVisible: false, sType: 'cmistype' },
                 { bVisible: false, sType: 'string' },
                 { aDataSort: [1, 2], asSorting: [ 'asc', 'desc' ],
                   sWidth: '31%' },
                 { aDataSort: [1, 4], asSorting: [ 'asc', 'desc' ],
                   sWidth: '8%'  },
                 { 'bVisible': false },
                 { 'bVisible': false },
                 { aDataSort: [5, 6, 1], asSorting: [ 'asc', 'desc' ],
                   sWidth: '18%'  },
                 { bVisible: false, sType: 'date'},
                 { aDataSort: [1, 8], asSorting: [ 'asc', 'desc' ],
                   sWidth: '12%'  }
             ],
             //{# see http://datatables.net/ref #}
             sPaginationType: "bootstrap",
             bFilter:         true,
             bLengthChange:   false,
             bStateSave:      true,
             iDisplayLength:  50,
             sDom:            'lrtip'
         },
             objectsTable = $('#objects-table').dataTable(dtParams);

         /* on page reload datatable keep previously filtered rows. Force
          refilter with current filter value */
         var filter = $('#filter');
         objectsTable.fnFilter(filter.val());

         /* check / uncheck all */
         function setSelected(checked) {
             $("input[name='object-selected']").prop('checked', checked);
         }

         $("a[href='#select-all']").click(function(e) {
             setSelected(true);
             e.preventDefault();
         });

         $("a[href='#unselect-all']").click(function(e) {
             setSelected(false);
             e.preventDefault();
         });

         /* enter key */
         filter.bind('keypress', function(e) {
             if (e.keyCode == 13) {
                 /* let return key for refilter */
                 objectsTable.fnFilter(this.value);
                 e.preventDefault();
             }
         });

         filter.bind('keyup', function(e) {
             if (e.keyCode == 13) {
                 e.preventDefault();
             }
             objectsTable.fnFilter(this.value);
         });

         /* actions */
         function onClickDelete(e) {
             e.preventDefault();
             var $button = $(this),
                 buttonForm = $(this.form),
                 msg = config.deleteConfirmMsg,
                 elements = $(document.forms['folder-listing'])
                     .find('input[name="object-selected"]:checked')
                     .closest('td')
                     .next('td'),
                 elList = $('<ul />').attr({'class': 'folder-items'});

             elements.each(function() {
                 var li = $('<li />').html($(this).html());
                 elList.append(li);
             });
             msg += $('<div />').append(elList).html();

             bootbox.confirm(
                 msg,
                 function(confirm) {
                     if (confirm) {
                         var actionVal = $('<input />',
                                            {'type':   'hidden',
                                             'name':  'action',
                                             'value': $button.attr('value')});
                         buttonForm.append(actionVal);
                         buttonForm.submit();
                     }
                 });
         }
         $('button.btn-danger[value="delete"]').click(onClickDelete);

         /* Move file functions */
         var moveFileFillListing = function(modal, folder_url) {
             var tbody = modal.find('tbody');
             var breadcrumbs = modal.find('ul.breadcrumb');

             $.ajax({
                 type:     'GET',
                 dataType: "json",
                 url:      folder_url,
                 cache:    false,
                 success:  function(data) {
                     var bc = $(data.breadcrumbs);
                     breadcrumbs.empty();

                     bc.each(function() {
                         var li = $('<li />');
                         var link = $('<a>' + this.title + '</a>')
                                 .attr('href', this.url)
                                 .attr('data-id', this.id);

                         link.appendTo(li);
                         li.appendTo(breadcrumbs);
                     });

                     var folders = $(data.folders);
                     tbody.empty();

                     folders.each(function() {
                         var tr = $('<tr />');
                         var td = $('<td />');
                         var link = $('<a>' + this.title + '</a>').attr('href', this.url)
                                 .attr('data-id', this.id)
                                 .appendTo(td);
                         td.append($('<span>/</span>').attr('class', 'divider'));
                         tr.append(td).appendTo(tbody);
                     });

                     var folderSelectable = data['current_folder_selectable'];
                     var button = $('#modal-move-button-submit');
                     button.attr('disabled', !folderSelectable);
                     if (!folderSelectable ^ button.hasClass('disabled')) {
                         button.toggleClass('disabled');
                     }
                 }
             });
         };

         $(document).on(
             'click',
             '#modal-move-files-directory-listing a',
             function(e) {
                 var self = $(this),
                     folder_id = self.attr('data-id'),
                     modal = $('#modal-move-files'),
                     url = self.attr('href');

                 modal.find('input[name="target-folder"]')
                     .attr('value', folder_id);

                 moveFileFillListing(modal, url);
                 e.preventDefault();
         });

         $('#modal-move-files').on('show.bs.modal', function() {
             var modal = $(this),
                 listing_form = $(document.forms["folder-listing"]),
                 elements = listing_form.find("input[name='object-selected']:checked"),
                 footer_inputs = $("#modal-move-files-inputs");

             footer_inputs.empty();
             elements.clone()
                 .attr('type', 'hidden')
                 .appendTo(footer_inputs);

             var target = $('<input />')
                     .attr({type: 'hidden',
                            name: 'target-folder',
                            value: ''});
             target.appendTo(footer_inputs);

             var l = document.location;
             /* don't use document.location + '/json': if anchors in url '/json'
              is ignored, ie http://.../folder#anchor */
             moveFileFillListing(
                 modal,
                 l.protocol + "//" + l.host + l.pathname + '/json' + l.search
             );
         });
     } // END setupFolderListing

     return setupFolderListing;
}));
