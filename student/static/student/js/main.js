// Main JavaScript file for ENSA Project Manager
// Contains common functionality used across multiple pages

// Alert message auto-dismiss functionality
$(document).ready(function() {
    // Auto-dismiss alert messages after 5 seconds
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);
    
    // Initialize any tooltips
    $('[data-toggle="tooltip"]').tooltip();
    
    // Initialize any datepickers
    if($.fn.datepicker) {
        $('.datepicker').datepicker({
            format: 'yyyy-mm-dd',
            autoclose: true
        });
    }
}); 