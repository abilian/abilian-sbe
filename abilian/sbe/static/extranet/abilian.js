/* Abilian namespace */
(function(Abilian, $) {

     /**
      * @define {?boolean} null if not set, false or true if explicitely set by
      * application. This variable should be set as soon as possible.
      */
     Abilian.DEBUG = null;

     /**
      * Initialize application parameters. Must be called when all resources are
      * loaded, but before any code is executed.
      */
     Abilian.init = function() {
         if (!Abilian.DEBUG) {
             /* deactivate datatable issuing 'alert' on any error in production.
              * It confuses users. */
             $.fn.dataTable.ext.sErrMode = '';   
         }
     };

     var widgets_creators = {};

     /**
      * @param create_fun: function(*params). Within function 'this' is set as
      * the item to widgetize wrapped with jQuery.
      */
     Abilian.register_widget_creator = function(name, create_fun) {
         widgets_creators[name] = create_fun;
     };

     /*
      * Initialiaze a single element.
      */
     Abilian.init_js_widget = function() {
         var $this = $(this);
         var creator_name = $this.data('initWith');
         var params = $this.data('initParams');

         if (!(params instanceof Array)) {
             params = new Array(params);
         }
         widgets_creators[creator_name].apply($this, params);
     };

     /*
      * Custom events
      */
     Abilian.events = {};
     Abilian.events.widgetsInitialized = 'widgets-initiliazed';

     /*
      * @define {Object} filled by custom code, holds information about current
      * logged user
      */
     Abilian.current_user = {
         crm: false          //has access to CRM?
     };

})(window.Abilian = window.Abilian || {}, jQuery);

Abilian.register_widget_creator('select2', function(params) { this.select2(params); });
