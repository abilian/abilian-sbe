// Tweaks for integrating datatables + bootstrap
/* Default class modification */
$.extend($.fn.dataTableExt.oStdClasses, {
  "sWrapper": "dataTables_wrapper form-inline"
});

/* API method to get paging information */
$.fn.dataTableExt.oApi.fnPagingInfo = function(oSettings) {
  return {
    "iStart":         oSettings._iDisplayStart,
    "iEnd":           oSettings.fnDisplayEnd(),
    "iLength":        oSettings._iDisplayLength,
    "iTotal":         oSettings.fnRecordsTotal(),
    "iFilteredTotal": oSettings.fnRecordsDisplay(),
    "iPage":          Math.ceil(oSettings._iDisplayStart / oSettings._iDisplayLength),
    "iTotalPages":    Math.ceil(oSettings.fnRecordsDisplay() / oSettings._iDisplayLength)
  };
};

/* Bootstrap style pagination control */
$.extend($.fn.dataTableExt.oPagination, {
  "bootstrap": {
    "fnInit": function(oSettings, nPaging, fnDraw) {
      var oLang = oSettings.oLanguage.oPaginate;
      var fnClickHandler = function(e) {
        e.preventDefault();
        if (oSettings.oApi._fnPageChange(oSettings, e.data.action)) {
          fnDraw(oSettings);
        }
      };

      $(nPaging).addClass('pagination').append(
          '<ul>' +
              '<li class="prev disabled"><a href="#">&larr; ' + oLang.sPrevious + '</a></li>' +
              '<li class="next disabled"><a href="#">' + oLang.sNext + ' &rarr; </a></li>' +
              '</ul>'
      );
      var els = $('a', nPaging);
      $(els[0]).bind('click.DT', { action: "previous" }, fnClickHandler);
      $(els[1]).bind('click.DT', { action: "next" }, fnClickHandler);
    },

    "fnUpdate": function(oSettings, fnDraw) {
      var iListLength = 5;
      var oPaging = oSettings.oInstance.fnPagingInfo();
      var an = oSettings.aanFeatures.p;
      var i, j, iLen, sClass, iStart, iEnd, iHalf = Math.floor(iListLength / 2);

      if (oPaging.iTotalPages < iListLength) {
        iStart = 1;
        iEnd = oPaging.iTotalPages;
      }
      else if (oPaging.iPage <= iHalf) {
        iStart = 1;
        iEnd = iListLength;
      } else if (oPaging.iPage >= (oPaging.iTotalPages - iHalf)) {
        iStart = oPaging.iTotalPages - iListLength + 1;
        iEnd = oPaging.iTotalPages;
      } else {
        iStart = oPaging.iPage - iHalf + 1;
        iEnd = iStart + iListLength - 1;
      }

      for (i = 0, iLen = an.length; i < iLen; i++) {
        // Remove the middle elements
        $('li:gt(0)', an[i]).filter(':not(:last)').remove();

        // Add the new list items and their event handlers
        for (j = iStart; j <= iEnd; j++) {
          sClass = (j == oPaging.iPage + 1) ? 'class="active"' : '';
          $('<li ' + sClass + '><a href="#">' + j + '</a></li>')
              .insertBefore($('li:last', an[i])[0])
              .bind('click', function(e) {
                e.preventDefault();
                oSettings._iDisplayStart = (parseInt($('a', this).text(), 10) - 1) * oPaging.iLength;
                fnDraw(oSettings);
              });
        }

        // Add / remove disabled classes from the static elements
        if (oPaging.iPage === 0) {
          $('li:first', an[i]).addClass('disabled');
        } else {
          $('li:first', an[i]).removeClass('disabled');
        }

        if (oPaging.iPage === oPaging.iTotalPages - 1 || oPaging.iTotalPages === 0) {
          $('li:last', an[i]).addClass('disabled');
        } else {
          $('li:last', an[i]).removeClass('disabled');
        }
      }
    }
  }
});

/* datatable: sort types and filters */
(function($) {
     $.extend($.fn.dataTableExt.oSort, {
               'string-non-null-pre': $.fn.dataTableExt.oSort['html-pre'],
               'string-non-null-asc': function(x, y)
                  {
                      if (x == y) { return 0; }
                      else if (x == '') { return -1; }
                      else if (y == '') { return 1; }
                      return $.fn.dataTableExt.oSort['string-asc'](x, y);
                  },
               'string-non-null-desc': function(x, y)
                  {
                      if (x == y) { return 0; }
                      else if (!x) { return 1; }
                      else if (!y) { return -1; }
                      return $.fn.dataTableExt.oSort['string-desc'](x, y);
                  },
               'cmistype-pre': $.fn.dataTableExt.oSort['string-pre'],
               'cmistype-asc': function(x, y)
                  {
                      if (x === y) { return 0; }
                      else if (x === 'folder') { return -1;}
                      else if (y === 'folder') { return 1;}
                      return 0;
                  },
               'cmistype-desc': function(x, y)
                  {
                      if (x == y) { return 0; }
                      else if (x === 'folder') { return -1;}
                      else if (y === 'folder') { return 1;}
                      return 0;
                  }
              });

})(jQuery);

/* datatable: advanced search */
(function($) {

	/**
	* Additional search criterias for DataTable with Ajax source
	*
	* @class AdvancedSearchFilters
	* @constructor
	* @param {object} oDTSettings Settings for the target DataTable.
	*/
    var AdvancedSearchFilters = function(oDTSettings) {
        var self = this;
        self.$Container = null;

        if (!(oDTSettings.oInit.bFilter
              && oDTSettings.oInit.bServerSide
              && oDTSettings.oInit.sAjaxSource
              && 'aoAdvancedSearchFilters' in oDTSettings.oInit
              && oDTSettings.oInit.aoAdvancedSearchFilters.length > 0)) {
            return;
        }

        self.aFilters = [];
        /* filters container */
        self.$Container = $('<div class="advanced-search-filters"></div>');
        var toggle_icon = $('<span />', {'class': 'icon-plus'});
        var sAdvSearch = oDTSettings.oLanguage.sAdvancedSearch || 'Advanced Search';
        var filters_container = $('<div />');
        filters_container.hide();
        var toggle = $('<span />')
            .css('cursor', 'pointer')        
            .append(sAdvSearch + '&nbsp;')
            .append(toggle_icon)
            .bind('click.DT',
                  {target: filters_container, icon: toggle_icon},
                  AdvancedSearchFilters.toggle);

        self.$Container.append(toggle, filters_container);

        /* create filters */
        var aoasf_len = oDTSettings.oInit.aoAdvancedSearchFilters.length;
        for (var i = 0; i < aoasf_len; i++) {
            var $criterion_container = $('<div></div>').attr({'class': 'criterion'});
            var filter = oDTSettings.oInit.aoAdvancedSearchFilters[i];
            var args = [].concat([filter.name, filter.label], filter.args);
            var func = AdvancedSearchFilters.oFilters[filter.type];
            self.aFilters.push(func.apply($criterion_container, args));
            filters_container.append($criterion_container);
        }

        oDTSettings.oInstance.bind('serverParams', {instance: self}, 
                                   AdvancedSearchFilters.serverParamsCallBack);
        self.$Container.on('redraw.DT', function() { oDTSettings.oInstance.fnDraw(); });
        self.$Container.on('change.DT',
                           'input, select',
                           function() { oDTSettings.oInstance.fnDraw(); });
    };

     /* filters registry A filter creates required inputs for filter 'name'; the
      * context is the container for this filter
      * @namespace
      */
     AdvancedSearchFilters.oFilters = {
         "text": function(name, label) {
             var self = this;

             if (label != "") {
                 self.append($('<label />')
                             .attr({'class': 'select inline span3 text-right'})
                             .css('cursor', 'default')
                             .append(
                                 $('<strong />').text(label))
                            );
             }

             var $input = $('<input />')
                 .attr({'type': 'text', 'name': name});
             self.append($input);

             return { 'name': name,
                      'val': function() { return [$input.val()]; }
             };
         },
         "radio": function(name, label) {
             var self = this;
             var checked = false;
             var len = arguments.length;

             if (label != "") {
                 self.append($('<label />')
                             .attr({'class': 'radio inline span3 text-right'})
                             .css('cursor', 'default')
                             .append(
                                 $('<strong />').text(label))
                            );
             }

             for (var i=2; i < len; i++) {
                 var arg = arguments[i];
                 var id = name + '_' + i;
                 var input = $('<input type="radio">')
                     .attr({'id': id,
                            'name': name,
                            'value': arg.value});

                 if (!checked && arg.checked) {
                     input.prop('checked', true);
                     checked = true;
                 }

                 var label = $('<label></label>')
                     .attr({'class': 'radio inline', 'for': id})
                     .text(arg.label)
                     .append(input);

                 self.append(label);
             }

             if (!checked) {
                 self.children('input').first().prop('checked', true);
             }

             return { "name": name,
                      "val": function() {return [self.find('input:checked').val()]; } 
                    };
         },
         "checkbox": function(name, label) {
             var self = this;
             var len = arguments.length;

             if (label != "") {
                 self.append($('<label />')
                             .attr({'class': 'checkbox inline span3 text-right'})
                             .css('cursor', 'default')
                             .append(
                                 $('<strong />').text(label))
                            );
             }

             for (var i=2; i < len; i++) {
                 var arg = arguments[i];
                 var id = name + '_' + (i-2);
                 var input = $('<input type="checkbox">')
                     .attr({'id': id,
                            'name': name,
                            'value': arg.value});

                 if (arg.checked) {
                     input.prop('checked', true);
                 }

                 var $label = $('<label></label>')
                     .attr({'class': 'checkbox inline', 'for': id})
                     .text(arg.label)
                     .append(input);

                 self.append($label);
             }

             return { "name": name,
                      "val": function() {
                          return self.find('input:checked')
                              .map(function(){return $(this).val();})
                              .get();
                      } 
                    };
         },
         'checkbox-select': function(name, label, args) {
             /* a checkbox with a select box activated only if checkbox is checked */
             var self = this;
             var $input = $('<input type="checkbox">')
                 .attr({'id': name,
                        'name': name,
                        'value': name,
                        'checked': 'checked'});
             var $label = $('<label></label>')
                 .attr({'class': 'checkbox inline span3 text-right', 'for': name})
                 .text(args.label)
                 .append($input);

             self.append($label);
            
             var select_id = name + '-select';
             var $select = $('<input />')
                 .attr({'id': select_id,
                        'name': select_id,
                        'type': 'hidden'});
             self.append($select);
             $select.select2({'data': args['select-data'],
                              'placeholder': (args['select-label'] || ''),
                              'allowClear': true,
                              'width': '20em',
                              'containerCss': {'margin-left': '0.5em'}
                             });


             $input.on('change', function(e) {
                           $select.select2('enable', this.checked);
                       });

             return { "name": name,
                      "val": function() {
                          if ($input.get(0).checked) {
                              return [$select.select2('val') || $input.val()];
                          }
                          return [];
                      } 
                    };             
         },
         'select': function(name, label, options, multiple) {
             var self = this;
             var len = arguments.length;
             multiple = multiple || false;
             
             if (label != "") {
                 self.append($('<label />')
                             .attr({'class': 'select inline span3 text-right'})
                             .css('cursor', 'default')
                             .append(
                                 $('<strong />').text(label))
                            );
             }
             var $select = $('<input />')
                 .attr({'id': name,
                        'name': name,
                        'type': 'hidden'});
             self.append($select);

             var s2_options = [];
             for (var i=0; i < options.length; i++) {
                 var opt = options[i];
                 s2_options.push({'id': opt[0], 'text': opt[1]});
             }

             $select.select2({'data': s2_options,
                              'placeholder': '',
                              'multiple': multiple,
                              'allowClear': true,
                              'width': '20em',
                              'containerCss': {'margin-left': '0.5em'} 
                             });
             return { 'name': name,
                      'val': function() {
                          return $select.data('select2').val();
                      }
             };
         },
         'optional_criterions': function(name, label) {
             var self = this;
             var arg_len = arguments.length;
             var $container = $('<div />')
                 .css('margin-bottom', '0.5em')
                 .append($('<span />').text(label + ':'));

             var $select = $('<select />')
                 .css('margin-left', '0.5em')
                 .append($('<option />'));
             
             for (var i=2; i < arg_len; i++) {
                 var args = arguments[i];
                 var $option = $('<option />')
                    .text(args.label)
                    .data(args)
                    .appendTo($select);
             }
             var criterions = {};

             $select.on('change',
                        function(e) {
                            e.preventDefault();
                            if (this.selectedIndex == 0) {
                                /* this is empty option */
                                return;
                            }

                            $(this).children('option:selected').each(
                                function() {
                                    var $option = $(this);
                                    var args = $option.data();
                                    var $container = $('<div />');
                                    var $remove_button = $('<button />')
                                        .attr({'class': 'close'})
                                        .append($('<span />').attr({'class': 'icon-remove'}))
                                        .on('click', function(e) {
                                                e.preventDefault();
                                                $container.remove();
                                                $option.show();
                                                delete criterions[args.value];
                                                self.trigger('redraw.DT');
                                            })
                                        .appendTo($container);
                                    $('<input />')
                                        .attr({'type': 'hidden',
                                               'name': name,
                                               'value': args.value})
                                        .appendTo($container);

                                    var func = AdvancedSearchFilters.oFilters[args.type];
                                    var filter_name = name + '.' + args.value;
                                    args.checked = true;
                                    criterions[args.value] = func.apply($container, [filter_name, '', args]);

                                    $option.hide();
                                    self.append($container);
                                });
                            this.selectedIndex = 0;
                        });

             $container.append($select);
             self.append($container);
             return { 'name': name,
                      'val': function() {
                          var result = { 'selected_filters' : [],
                                         'values': {}};

                          for (var filter_name in criterions) {
                              result.selected_filters.push(filter_name);
                              result.values[filter_name] = criterions[filter_name].val();
                          }
                          return [JSON.stringify(result)];
                      }
             };
         }
     };

	/**
	* Get the container node of the advanced search filters
	* 
	* @method
	* @return {Node} The container node.
	*/
	AdvancedSearchFilters.prototype.getContainer = function() {
		return this.$Container && this.$Container.get(0);
	};

     /**
      * show / hide filters
      */
     AdvancedSearchFilters.toggle = function(e) {
         var target = e.data.target;
         var icon = e.data.icon;
         var should_show = icon.hasClass('icon-plus');
         var is_visible = target.is(':visible');
         var new_class = should_show ? 'icon-minus' : 'icon-plus';
         icon.toggleClass('icon-plus', !should_show);
         icon.toggleClass('icon-minus', should_show);

         // if 'is_visible' differ from 'should_show' (logical XOR)
         if ((is_visible || should_show) && !(is_visible && should_show)) {
             target.slideToggle(200);
         }
         e.preventDefault();
     };

     /**
      * Callback to fill server params before ajax request
      */
     AdvancedSearchFilters.serverParamsCallBack = function(event, aoData) {
         var self = event.data.instance;
         for(var i=0; i < self.aFilters.length; i++) {
             var f = self.aFilters[i];
             var vals = f.val();
             if (!(vals instanceof Array)) {
                 vals = [vals];
             }
             $(vals).each(function() { aoData.push({name: f.name, value: this});});
         }
     };

	/*
	 * Register a new feature with DataTables
	 */
	if ( typeof $.fn.dataTable === 'function'
         && typeof $.fn.dataTableExt.fnVersionCheck === 'function'
         && $.fn.dataTableExt.fnVersionCheck('1.7.0') ) {

		$.fn.dataTableExt.aoFeatures.push( {
			'fnInit': function( oDTSettings ) {
				var asf = new AdvancedSearchFilters(oDTSettings);
				return asf.getContainer();
			},
			'cFeature': 'F',
			'sFeature': 'AdvancedSearchFilters'
		} );
	} else {
		throw 'Warning: AdvancedSearchFilters requires DataTables 1.7 or greater - www.datatables.net/download';
	}

     /*
      * setup useable href arguments according to current table filters criterions.
      * Used for CRM/Excel export
      */
     var dataTableSetExportArgs = function(e) {
         var tbl = $(e.target).dataTable();
         var settings = tbl.fnSettings();
         var params = tbl._fnAjaxParameters(settings);
         tbl._fnServerParams(params);
         $.data(e.target, 'current-query-args', params);
         return false;
     };
     $.fn.dataTableSetExportArgs = dataTableSetExportArgs;

}(jQuery));

