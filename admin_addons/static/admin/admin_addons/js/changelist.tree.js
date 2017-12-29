var ChangeListTree = ( function( $ ) {
    'use strict';

    var $table;
    var $rows;
    var $doc = $( document );

    $doc.ready( init );

    function init() {
        $table = $( '#result_list' );
        if( $table.length === 1 ) {
            $rows = $( '[class^="row"]', $table );
            $rows.each( init_row );
        }
    };

    function init_row() {
        var $this = $( this );
        this.$icon = $( '.admin-addons-icon-button', $this );
        this.$open_col = $( '.field-__str__', $this );
        this.$open_col.html(
            '<a href="' + this.$icon.data('list-url') + '">' + this.$open_col.html() + '</a>'
        );
    }

})( django.jQuery );