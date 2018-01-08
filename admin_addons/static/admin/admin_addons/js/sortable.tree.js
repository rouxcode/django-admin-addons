var SortableTree = ( function( $ ) {
    'use strict';

    var csrftoken;
    var current_page;
    var sortable;
    var total_pages;
    var update_url;
    var wrap;
    var $items;
    var $wrap;

    var handle_class = 'admin-addons-drag';
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
                // forceFallback: false,
                // fallbackTolerance: 5,
                handle: '.' + handle_class,
                ghostClass: "sortable-ghost",
                chosenClass: "sortable-chosen",
                onUpdate: update
            } );
        }
    };

    function init_item( i ) {
        var item = this;
        item.$ = $( this );
        item.$drag = $( '.' + handle_class, item.$ );
        item._opts = {
            index: i,
            pk: item.$drag.data( 'pk' ),
            depth: item.$drag.data( 'depth' ),
            parent: item.$drag.data( 'parent' )
        };
        item.$.addClass( draggable_class );

        item.$edit = $( 'a:first', item.$ );
        item.$edit_col = item.$edit.parent();
        item.$edit_col[0]._url = item.$edit.attr( 'href' );
        item.$edit_col.addClass( 'field-col_select_node' );
        item.$edit_col.on( 'click', edit_item );

        return item;
    };

    function edit_item( e ) {
        window.location = this._url;
    };

    function set_item_index( i ) {
        this._opts.index = i;
        return this
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
    };

    return {
        options: set_options
    };

} )( django.jQuery );
