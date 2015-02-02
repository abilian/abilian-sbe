/* datatable: sort types and filters */
(function(window, document, undefined) {

    (function(factory) {
	    'use strict';

	    // Using requirejs?
	    if ( typeof define === 'function' && define.amd )
	    {
		    requirejs(['jquery', 'jquery.dataTables'], factory );
	    }
	    else {
		    factory(jQuery);
	    }
    }
(function($) {
	'use strict';
    var FOLDER_TYPE = 'abilian.sbe.apps.documents.models.folder';

    function sortFolderFirstCmp(x, y) {
        if (x === y) { return 0; }
        else if (x === FOLDER_TYPE) { return -1;}
        else if (y === FOLDER_TYPE) { return 1;}
        return 0;
    };

     $.extend($.fn.dataTableExt.oSort, {
               'cmistype-pre': $.fn.dataTableExt.oSort['string-pre'],
               'cmistype-asc': sortFolderFirstCmp,
               'cmistype-desc': sortFolderFirstCmp,
              });

}));

}(window, document));
