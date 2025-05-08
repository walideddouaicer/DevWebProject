/**
 * Configuration for Select2 dropdown components
 * Used primarily for collaborator selection in project forms
 */
$(document).ready(function() {
    // Initialize collaborators select field
    $('#id_collaborators').select2({
        placeholder: 'Rechercher un collaborateur...',
        allowClear: true,
        width: '100%',
        maximumSelectionLength: 10,
        templateResult: formatResult,
        templateSelection: formatSelection,
        language: {
            maximumSelected: function() {
                return "Vous pouvez sélectionner 10 collaborateurs maximum";
            }
        }
    });

    // Format the display of student results in dropdown
    function formatResult(student) {
        if (!student.id) return student.text;
        const match = student.text.match(/(.+) \((\d+)\)/);
        if (match) {
            const name = match[1];
            const id = match[2];
            return $(
                `<div class="student-result">
                    <div class="student-name">${name}</div>
                    <div class="student-info">ID: ${id}</div>
                </div>`
            );
        }
        return student.text;
    }

    // Format the display of selected students
    function formatSelection(student) {
        return student.text;
    }
}); 