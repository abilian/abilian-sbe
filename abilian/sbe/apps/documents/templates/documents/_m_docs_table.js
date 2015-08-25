
(
function() {
function setupDocTable(Abilian, $, jqDT, bootbox) {
    'use strict';
    Abilian.fn.onAppInit(function() {

        $.fn.dataTableExt.afnFiltering.push(
            function(oSettings, aData, iDataIndex) {
                var filter_value = $("#filter").val();
                var row_text = aData[2].trim();
                return row_text.match(new RegExp(filter_value, "i"));
            }
        );

        var objects_table = $('#objects-table').dataTable({
            aoColumns: [
                { asSorting: [], sWidth: "1%" },
                { bVisible: false, sType: "cmistype" },
                { bVisible: false, sType: "string" },
                { aDataSort: [1, 2], asSorting: [ "asc", "desc" ], sWidth: "31%" },
                { aDataSort: [1, 4], asSorting: [ "asc", "desc" ], sWidth: "8%"  },
                { aDataSort: [1, 5], asSorting: [ "asc", "desc" ], sWidth: "18%"  },
                { bVisible: false, sType: "date"},
                { aDataSort: [1, 6], asSorting: [ "asc", "desc" ], sWidth: "12%"  }
            ],
            //{# see http://datatables.net/ref #}

            sPaginationType: "bootstrap",
            bFilter:         true,
            bLengthChange:   false,
            bStateSave:      true,
            iDisplayLength:  50,
            sDom:            'lrtip'
        });

        /* on page reload datatable keep previously filtered rows. Force
           refilter with current filter value */
        var filter = $('#filter');
        objects_table.fnFilter(filter.val());

        $("a[href='#select-all']").click(function(e) {
            $("input[name='object-selected']").prop('checked', true);
            e.preventDefault();
        });
        $("a[href='#unselect-all']").click(function(e) {
            $("input[name='object-selected']").prop('checked', false);
            e.preventDefault();
        });

        filter.bind('keypress', function(e) {
            if (e.keyCode == 13) {
                /* let return key for refilter */
                objects_table.fnFilter(this.value);
                e.preventDefault();
            }
        });

        filter.bind('keyup', function(e) {
            if (e.keyCode == 13) {
                e.preventDefault();
            }
            objects_table.fnFilter(this.value);
        });

        $('button.btn-danger[value="delete"]').click(function(e) {
            e.preventDefault();
            var $button = $(this);
            var button_form = $(this.form);
            var msg = "{{ _("Delete selected elements?") }}";
            var elements = $(document.forms["folder-listing"])
                                     .find("input[name='object-selected']")
                                     .filter(function() { return this.checked; })
                                     .closest('td')
                                     .next('td');
            var el_list = $('<ul />').attr({'class': 'folder-items'});

            elements.each(function() {
                var li = $('<li />').html($(this).html());
                el_list.append(li);
            });
            msg += $('<div />').append(el_list).html();

            bootbox.confirm(
                msg,
                function(confirm) {
                    if (confirm) {
                        var action_val = $('<input />',
                                           {'type':   'hidden',
                                            'name':  'action',
                                            'value': $button.attr('value')});
                        button_form.append(action_val);
                        button_form.submit();
                    }
                });
        });

        /* Move file functions */
        var move_file_fill_listing = function(modal, folder_url) {
            var tbody = modal.find('tbody');
            var breadcrumbs = modal.find('ul.breadcrumb');

            $.ajax({
                type:     'GET',
                dataType: "json",
                url:      folder_url,
                cache:    false,
                success:  function(data) {
                    var bc = $(data['breadcrumbs']);
                    breadcrumbs.empty();

                    bc.each(function(index) {
                        var li = $('<li />');
                        var link = $('<a>' + this.title + '</a>')
                                                 .attr('href', this.url)
                                                 .attr('data-id', this.id)
                                                 .appendTo(li);
                        li.appendTo(breadcrumbs);
                    });

                    var folders = $(data['folders']);
                    tbody.empty();

                    folders.each(function(index) {
                        var tr = $('<tr />');
                        var td = $('<td />');
                        var link = $('<a>' + this.title + '</a>').attr('href', this.url)
                                                 .attr('data-id', this.id)
                                                 .appendTo(td);
                        td.append($('<span>/</span>').attr('class', 'divider'));
                        tr.append(td).appendTo(tbody);
                    });

                    var folder_selectable = data['current_folder_selectable'];
                    var button = $('#modal-move-button-submit');
                    button.attr('disabled', !folder_selectable);
                    if (!folder_selectable ^ button.hasClass('disabled')) {
                        button.toggleClass('disabled');
                    }
                }
            });
        };

        $(document).on('click', '#modal-move-files-directory-listing a', function(e) {
            var self = $(this);
            var folder_id = self.attr('data-id');
            var modal = $('#modal-move-files');
            modal.find('input[name="target-folder"]').attr('value', folder_id);
            var url = self.attr('href');
            move_file_fill_listing(modal, url);
            e.preventDefault();
        });

        $('#modal-move-files').on('show.bs.modal', function() {
            var modal = $(this);
            var listing_form = $(document.forms["folder-listing"]);
            var elements = listing_form.find("input[name='object-selected']")
                                       .filter(function() {
                                           return this.checked;
                                       });
            var footer_inputs = $("#modal-move-files-inputs");
            footer_inputs.empty();
            elements.clone().attr('type', 'hidden').appendTo(footer_inputs);
            var target = $('<input />')
                      .attr({type: 'hidden',
                             name: 'target-folder',
                             value: ''})
                      .appendTo(footer_inputs);
            var l = document.location;
            {# don't use document.location + '/json': if anchors in url '/json' is
              ignored, ie http://.../folder#anchor
              #}
              move_file_fill_listing(modal, l.protocol + "//" + l.host + l.pathname + '/json' + l.search);
            });
        });
    }

    require(['Abilian', 'jquery', 'jquery.dataTables', 'bootbox'], setupDocTable);
}());
