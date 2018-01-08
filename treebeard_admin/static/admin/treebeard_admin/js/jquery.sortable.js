/*
 MIT
*/
(function(c){"function"===typeof define&&define.amd?define(["jquery"],c):c(jQuery)})(function(c){c.fn.sortable=function(b){var d,f=arguments;this.each(function(){var e=c(this),a=e.data("sortable");a||!(b instanceof Object)&&b||(a=new Sortable(this,b),e.data("sortable",a));if(a){if("widget"===b)return a;"destroy"===b?(a.destroy(),e.removeData("sortable")):"function"===typeof a[b]?d=a[b].apply(a,[].slice.call(f,1)):b in a.options&&(d=a.option.apply(a,f))}});return void 0===d?this:d}});