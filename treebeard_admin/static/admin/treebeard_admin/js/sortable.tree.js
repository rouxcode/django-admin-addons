var SortableTree = ( function( $ ) {
    'use strict';

    var csrftoken;
    var current_page;
    var max_depth;
    var sortable;
    var total_pages;
    var update_url;
    var wrap;
    var $items;
    var $wrap;

    var handle_class = 'treebeard-admin-drag';
    var draggable_class = 'draggable-item';
    var $doc = $( document );

    $doc.ready( init );

    function init() {
        $( '#result_list' ).addClass( 'sortable-tree' );
        $wrap = $( '#result_list tbody' );

        if( $wrap.length > 0 ) {
            wrap = $wrap[ 0 ];
            $items = $( '.row1, .row2', $wrap ).each( init_item );
            sortable = new Sortable( wrap, {
                draggable: "." + draggable_class,
                handle: '.' + handle_class,
                ghostClass: "treebeard-admin-ghost",
                chosenClass: "treebeard-admin-chosen",
                onUpdate: update
            } );
        }
    };

    function init_item( i ) {
        var item = this;
        item.$ = $( this );
        item.$drag = $( '.' + handle_class, item.$ );
        item.$icon = $( '.treebeard-admin-icon-button', item.$ );
        item.$open_col = $( '.field-__str__', item.$ );
        item._opts = {
            index: i,
            pk: item.$drag.data( 'pk' ),
            depth: item.$drag.data( 'depth' ),
            parent: item.$drag.data( 'parent' )
        };
        item.$.addClass( draggable_class );

        if( max_depth == 0 || item._opts.depth <= max_depth  ) {
            item.$open_col.html(
                '<a href="' + item.$icon.data('list-url') + '">'
                + item.$open_col.html()
                + '</a>'
            );
        }
        return item;
    };

    function set_item_index( i ) {
        this._opts.index = i;
        this.$.removeClass( 'row1 row2' );
        this.$.addClass( i % 2 == 0 ? 'row1' : 'row2' );
        return this;
    };

    function update( e ) {
        if ( e.oldIndex != e.newIndex ) {
            var item = e.item;
            var index = e.newIndex;
            var $list = $( '.' + draggable_class, $wrap );
            var data = {
                node: item._opts.pk,
                depth: item._opts.depth,
                csrfmiddlewaretoken: csrftoken
            };
            if( item._opts.parent ) {
                data.parent = item._opts.parent;
            }
            if( index === 0  ) {
                data.pos = 'first';
                data.target = $list[1]._opts.pk;
            } else if( index + 1 === $list.length  ) {
                data.pos = 'last';
                data.target = $list[1]._opts.pk;
            } else {
                data.pos = 'right';
                data.target = $list[ index - 1 ]._opts.pk;
            }
            $.ajax( {
                url: update_url,
                type: 'POST',
                data: data
            } ).fail( function() {
                show_error( 'there has been a problem sorting the items' );
            } ).done( function( data ) {
                $items = $( '.' + draggable_class, $wrap );
                $items.each( set_item_index );
                if( data.message === 'error' ) {
                    show_error( data.error );
                }
            } );
        }
    };

    // Messaging

    function show_error( msg ) {
        // TODO implement nice html message
        console.error( msg );
    }


    // Utilities --------------------------------------------------------------

    function set_options( options ) {
        // TODO check if option has value & do proper init or error handling
        csrftoken = options.csrftoken;
        current_page = options.current_page;
        total_pages = options.total_pages;
        update_url = options.update_url;
        max_depth = options.max_depth || 0;
    };

    return {
        options: set_options
    };

} )( django.jQuery );
