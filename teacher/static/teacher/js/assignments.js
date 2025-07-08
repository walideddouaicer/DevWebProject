/**
 * Assignment management JavaScript for teachers
 */

// Assignment Form Dynamic Behavior
function toggleAssignmentOptions(assignmentType) {
    const choiceBasedOptions = document.getElementById('choice-based-options');
    const directOptions = document.getElementById('direct-options');
    
    if (assignmentType === 'choice_based') {
        if (choiceBasedOptions) choiceBasedOptions.style.display = 'block';
        if (directOptions) directOptions.style.display = 'none';
    } else if (assignmentType === 'direct') {
        if (choiceBasedOptions) choiceBasedOptions.style.display = 'none';
        if (directOptions) directOptions.style.display = 'block';
    } else {
        if (choiceBasedOptions) choiceBasedOptions.style.display = 'none';
        if (directOptions) directOptions.style.display = 'none';
    }
}

function toggleGroupOptions(isGroupWork) {
    const groupOptions = document.getElementById('group-options');
    const groupFormationDeadline = document.getElementById('group-formation-deadline-field');
    
    if (isGroupWork) {
        if (groupOptions) groupOptions.style.display = 'block';
        if (groupFormationDeadline) groupFormationDeadline.style.display = 'block';
    } else {
        if (groupOptions) groupOptions.style.display = 'none';
        if (groupFormationDeadline) groupFormationDeadline.style.display = 'none';
    }
}

function toggleMaxGroups(isUnique) {
    const maxGroupsField = document.getElementById('max-groups-field');
    if (maxGroupsField) {
        maxGroupsField.style.display = isUnique ? 'none' : 'block';
    }
}

// Project Option Management
function addProjectOption() {
    const container = document.getElementById('project-options-container');
    const template = document.getElementById('option-template');
    
    if (container && template) {
        const clone = template.content.cloneNode(true);
        container.appendChild(clone);
    }
}

function removeProjectOption(button) {
    const optionItem = button.closest('.project-option-item');
    if (optionItem && confirm('Êtes-vous sûr de vouloir supprimer cette option ?')) {
        optionItem.remove();
    }
}

// Student Selection Management
function toggleStudentSelection(checkbox) {
    const studentId = checkbox.value;
    const studentCard = checkbox.closest('.student-card');
    
    if (checkbox.checked) {
        studentCard?.classList.add('selected');
    } else {
        studentCard?.classList.remove('selected');
    }
    
    updateSelectedCount();
}

function selectAllStudents() {
    const checkboxes = document.querySelectorAll('.student-checkbox:not(:disabled)');
    const selectAllBtn = document.getElementById('select-all-btn');
    
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = !allChecked;
        toggleStudentSelection(checkbox);
    });
    
    selectAllBtn.textContent = allChecked ? 'Tout sélectionner' : 'Tout désélectionner';
}

function updateSelectedCount() {
    const selectedCheckboxes = document.querySelectorAll('.student-checkbox:checked');
    const countElement = document.getElementById('selected-count');
    
    if (countElement) {
        countElement.textContent = selectedCheckboxes.length;
    }
}

// Assignment Publishing
function publishAssignment(assignmentId) {
    if (confirm('Êtes-vous sûr de vouloir publier ce devoir ? Les étudiants pourront le voir immédiatement.')) {
        // Show loading state
        const publishBtn = event.target;
        const originalText = publishBtn.innerHTML;
        publishBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Publication...';
        publishBtn.disabled = true;
        
        // Submit form or make AJAX request
        const form = document.getElementById('publish-form');
        if (form) {
            form.submit();
        }
    }
}

// Progress Tracking
function updateProgressDisplay() {
    const progressCards = document.querySelectorAll('.progress-card');
    
    progressCards.forEach(card => {
        const value = card.querySelector('.progress-value');
        const currentValue = parseInt(value.textContent);
        
        // Animate counter
        animateCounter(value, 0, currentValue, 1000);
    });
}

function animateCounter(element, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const currentValue = Math.floor(progress * (end - start) + start);
        element.textContent = currentValue;
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

// Group Management
function showGroupDetails(groupId) {
    const modal = document.getElementById('group-details-modal');
    const modalContent = document.getElementById('group-details-content');
    
    if (modal && modalContent) {
        // Fetch group details via AJAX
        fetch(`/teacher/assignments/groups/${groupId}/details/`)
            .then(response => response.json())
            .then(data => {
                modalContent.innerHTML = data.html;
                modal.style.display = 'block';
            })
            .catch(error => {
                console.error('Error fetching group details:', error);
                alert('Erreur lors du chargement des détails du groupe');
            });
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

// Search and Filter
function initializeSearchAndFilter() {
    const searchInput = document.getElementById('assignment-search');
    const filterSelects = document.querySelectorAll('.filter-select');
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterAssignments, 300));
    }
    
    filterSelects.forEach(select => {
        select.addEventListener('change', filterAssignments);
    });
}

function filterAssignments() {
    const searchTerm = document.getElementById('assignment-search')?.value.toLowerCase() || '';
    const statusFilter = document.getElementById('status-filter')?.value || '';
    const typeFilter = document.getElementById('type-filter')?.value || '';
    const moduleFilter = document.getElementById('module-filter')?.value || '';
    
    const assignmentItems = document.querySelectorAll('.assignment-item');
    
    assignmentItems.forEach(item => {
        const title = item.querySelector('.assignment-title')?.textContent.toLowerCase() || '';
        const status = item.dataset.status || '';
        const type = item.dataset.type || '';
        const module = item.dataset.module || '';
        
        const matchesSearch = title.includes(searchTerm);
        const matchesStatus = !statusFilter || status === statusFilter;
        const matchesType = !typeFilter || type === typeFilter;
        const matchesModule = !moduleFilter || module === moduleFilter;
        
        if (matchesSearch && matchesStatus && matchesType && matchesModule) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
    
    updateResultsCount();
}

function updateResultsCount() {
    const visibleItems = document.querySelectorAll('.assignment-item[style="display: flex"], .assignment-item:not([style*="display: none"])');
    const countElement = document.getElementById('results-count');
    
    if (countElement) {
        countElement.textContent = `${visibleItems.length} résultat(s)`;
    }
}

// Utility Functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('fr-FR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getTimeRemaining(deadline) {
    const now = new Date();
    const deadlineDate = new Date(deadline);
    const diff = deadlineDate - now;
    
    if (diff <= 0) return 'Échue';
    
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    
    if (days > 0) {
        return `${days} jour${days > 1 ? 's' : ''}`;
    } else if (hours > 0) {
        return `${hours} heure${hours > 1 ? 's' : ''}`;
    } else {
        return 'Moins d\'une heure';
    }
}

// Form Validation
function validateAssignmentForm() {
    const form = document.getElementById('assignment-form');
    if (!form) return true;
    
    const title = form.querySelector('[name="title"]')?.value.trim();
    const deadline = form.querySelector('[name="deadline"]')?.value;
    const assignmentType = form.querySelector('[name="assignment_type"]')?.value;
    const isGroupWork = form.querySelector('[name="is_group_work"]')?.checked;
    
    let isValid = true;
    let errors = [];
    
    if (!title) {
        errors.push('Le titre est obligatoire');
        isValid = false;
    }
    
    if (!deadline) {
        errors.push('La date limite est obligatoire');
        isValid = false;
    } else {
        const deadlineDate = new Date(deadline);
        const now = new Date();
        if (deadlineDate <= now) {
            errors.push('La date limite doit être dans le futur');
            isValid = false;
        }
    }
    
    if (assignmentType === 'choice_based') {
        const optionsCount = document.querySelectorAll('.project-option-item:not(.template)').length;
        if (optionsCount === 0) {
            errors.push('Au moins une option de projet est requise pour les devoirs à choix multiple');
            isValid = false;
        }
    }
    
    if (isGroupWork) {
        const minSize = parseInt(form.querySelector('[name="min_group_size"]')?.value) || 0;
        const maxSize = parseInt(form.querySelector('[name="max_group_size"]')?.value) || 0;
        
        if (minSize < 2) {
            errors.push('La taille minimale d\'un groupe doit être d\'au moins 2');
            isValid = false;
        }
        
        if (maxSize < minSize) {
            errors.push('La taille maximale doit être supérieure ou égale à la taille minimale');
            isValid = false;
        }
    }
    
    if (!isValid) {
        alert('Erreurs de validation :\n' + errors.join('\n'));
    }
    
    return isValid;
}

// Auto-save functionality
function initializeAutoSave() {
    const form = document.getElementById('assignment-form');
    if (!form) return;
    
    const formInputs = form.querySelectorAll('input, select, textarea');
    
    formInputs.forEach(input => {
        input.addEventListener('change', debounce(autoSave, 2000));
    });
}

function autoSave() {
    const form = document.getElementById('assignment-form');
    if (!form) return;
    
    const formData = new FormData(form);
    formData.append('auto_save', 'true');
    
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAutoSaveIndicator();
        }
    })
    .catch(error => {
        console.error('Auto-save failed:', error);
    });
}

function showAutoSaveIndicator() {
    const indicator = document.getElementById('auto-save-indicator');
    if (indicator) {
        indicator.style.display = 'block';
        indicator.style.opacity = '1';
        
        setTimeout(() => {
            indicator.style.opacity = '0';
            setTimeout(() => {
                indicator.style.display = 'none';
            }, 300);
        }, 2000);
    }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize form behavior
    const assignmentTypeSelect = document.getElementById('id_assignment_type');
    if (assignmentTypeSelect) {
        assignmentTypeSelect.addEventListener('change', (e) => {
            toggleAssignmentOptions(e.target.value);
        });
        
        // Initialize on page load
        toggleAssignmentOptions(assignmentTypeSelect.value);
    }
    
    const isGroupWorkCheckbox = document.getElementById('id_is_group_work');
    if (isGroupWorkCheckbox) {
        isGroupWorkCheckbox.addEventListener('change', (e) => {
            toggleGroupOptions(e.target.checked);
        });
        
        // Initialize on page load
        toggleGroupOptions(isGroupWorkCheckbox.checked);
    }
    
    // Initialize unique checkbox for project options
    const isUniqueCheckboxes = document.querySelectorAll('[name$="-is_unique"]');
    isUniqueCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const maxGroupsField = e.target.closest('.project-option-item')?.querySelector('[name$="-max_groups"]')?.closest('.form-group');
            if (maxGroupsField) {
                maxGroupsField.style.display = e.target.checked ? 'none' : 'block';
            }
        });
    });
    
    // Initialize search and filter
    initializeSearchAndFilter();
    
    // Initialize auto-save
    initializeAutoSave();
    
    // Initialize progress display
    updateProgressDisplay();
    
    // Initialize tooltips
    initializeTooltips();
    
    // Update selected count on page load
    updateSelectedCount();
});

// Tooltip initialization
function initializeTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(event) {
    const text = event.target.getAttribute('data-tooltip');
    if (!text) return;
    
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = text;
    tooltip.style.position = 'absolute';
    tooltip.style.background = '#333';
    tooltip.style.color = 'white';
    tooltip.style.padding = '8px 12px';
    tooltip.style.borderRadius = '4px';
    tooltip.style.fontSize = '12px';
    tooltip.style.zIndex = '1000';
    tooltip.style.pointerEvents = 'none';
    
    document.body.appendChild(tooltip);
    
    const rect = event.target.getBoundingClientRect();
    tooltip.style.top = (rect.top - tooltip.offsetHeight - 8) + 'px';
    tooltip.style.left = (rect.left + rect.width / 2 - tooltip.offsetWidth / 2) + 'px';
    
    event.target._tooltip = tooltip;
}

function hideTooltip(event) {
    if (event.target._tooltip) {
        event.target._tooltip.remove();
        delete event.target._tooltip;
    }
}

// Export functions for global access
window.AssignmentManager = {
    toggleAssignmentOptions,
    toggleGroupOptions,
    toggleMaxGroups,
    addProjectOption,
    removeProjectOption,
    toggleStudentSelection,
    selectAllStudents,
    publishAssignment,
    showGroupDetails,
    closeModal,
    validateAssignmentForm
};