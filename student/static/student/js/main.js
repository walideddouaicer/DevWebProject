/**
 * Main JavaScript - App Initialization & Interactive Components
 */

// App initialization
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    console.log('🚀 ENSA Project Manager - Initializing...');
    
    // Initialize components
    initializeSidebar();
    initializeNavigation();
    initializeTabs();
    initializeSearch();
    initializeTooltips();
    initializeAnimations();
    initializeAccessibility();
    
    console.log('✅ App initialized successfully!');
}

/**
 * Sidebar Management
 */
function initializeSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const mobileOverlay = document.querySelector('.mobile-overlay');
    
    if (!sidebar) return;
    
    // Create mobile overlay if it doesn't exist
    if (!mobileOverlay) {
        const overlay = document.createElement('div');
        overlay.className = 'mobile-overlay';
        document.body.appendChild(overlay);
        
        // Close sidebar when overlay is clicked
        overlay.addEventListener('click', closeMobileSidebar);
    }
    
    // Sidebar toggle functionality
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', toggleMobileSidebar);
    }
    
    // Close sidebar on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeMobileSidebar();
        }
    });
    
    // Handle window resize
    window.addEventListener('resize', handleSidebarResize);
    
    function toggleMobileSidebar() {
        sidebar.classList.toggle('mobile-open');
        document.querySelector('.mobile-overlay')?.classList.toggle('active');
        document.body.style.overflow = sidebar.classList.contains('mobile-open') ? 'hidden' : '';
        
        // Update aria-expanded
        const isOpen = sidebar.classList.contains('mobile-open');
        sidebarToggle?.setAttribute('aria-expanded', isOpen);
    }
    
    function closeMobileSidebar() {
        sidebar.classList.remove('mobile-open');
        document.querySelector('.mobile-overlay')?.classList.remove('active');
        document.body.style.overflow = '';
        sidebarToggle?.setAttribute('aria-expanded', 'false');
    }
    
    function handleSidebarResize() {
        if (window.innerWidth > 768) {
            closeMobileSidebar();
        }
    }
}

/**
 * Navigation Management
 */
function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        // Add click handler for non-link nav items
        if (!item.href && !item.querySelector('a')) {
            item.addEventListener('click', handleNavItemClick);
        }
        
        // Add keyboard navigation
        item.addEventListener('keydown', handleNavKeydown);
    });
    
    function handleNavItemClick(e) {
        e.preventDefault();
        
        // Remove active class from all items
        navItems.forEach(nav => nav.classList.remove('active'));
        
        // Add active class to clicked item
        e.currentTarget.classList.add('active');
        
        // Animate the item
        animateNavItem(e.currentTarget);
    }
    
    function handleNavKeydown(e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            e.currentTarget.click();
        }
    }
    
    function animateNavItem(item) {
        item.style.transform = 'translateX(8px)';
        setTimeout(() => {
            item.style.transform = '';
        }, 150);
    }
}

/**
 * Tab System
 */
function initializeTabs() {
    const tabSystems = document.querySelectorAll('.tab-system');
    
    tabSystems.forEach(system => {
        const tabButtons = system.querySelectorAll('.tab-button');
        const tabContents = system.querySelectorAll('.tab-content');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.getAttribute('data-tab');
                
                // Remove active class from all buttons and contents
                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));
                
                // Add active class to clicked button
                button.classList.add('active');
                
                // Show corresponding tab content
                const targetContent = system.querySelector(`#${tabId}-tab`);
                if (targetContent) {
                    targetContent.classList.add('active');
                    
                    // Animate content
                    targetContent.style.opacity = '0';
                    targetContent.style.transform = 'translateY(10px)';
                    
                    requestAnimationFrame(() => {
                        targetContent.style.transition = 'all 0.3s ease';
                        targetContent.style.opacity = '1';
                        targetContent.style.transform = 'translateY(0)';
                    });
                }
                
                // Update URL hash for deep linking
                if (history.replaceState) {
                    history.replaceState(null, null, `#${tabId}`);
                }
            });
            
            // Keyboard support
            button.addEventListener('keydown', (e) => {
                if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                    e.preventDefault();
                    const buttons = Array.from(tabButtons);
                    const currentIndex = buttons.indexOf(button);
                    const nextIndex = e.key === 'ArrowLeft' 
                        ? (currentIndex - 1 + buttons.length) % buttons.length
                        : (currentIndex + 1) % buttons.length;
                    
                    buttons[nextIndex].click();
                    buttons[nextIndex].focus();
                }
            });
        });
        
        // Handle URL hash on page load
        const hash = window.location.hash.replace('#', '');
        if (hash) {
            const targetButton = system.querySelector(`[data-tab="${hash}"]`);
            if (targetButton) {
                targetButton.click();
            }
        }
    });
}

/**
 * Search Functionality
 */
function initializeSearch() {
    const searchInputs = document.querySelectorAll('.search-input');
    
    searchInputs.forEach(input => {
        let searchTimeout;
        
        input.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            
            // Debounce search
            searchTimeout = setTimeout(() => {
                handleSearch(e.target.value);
            }, 300);
        });
        
        // Clear search on escape
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                input.value = '';
                handleSearch('');
                input.blur();
            }
        });
    });
    
    function handleSearch(query) {
        // Emit custom search event
        const event = new CustomEvent('searchQuery', {
            detail: { query }
        });
        document.dispatchEvent(event);
    }
}

/**
 * Tooltip Management
 */
function initializeTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
        element.addEventListener('focus', showTooltip);
        element.addEventListener('blur', hideTooltip);
    });
    
    function showTooltip(e) {
        const element = e.currentTarget;
        const tooltip = element.getAttribute('data-tooltip');
        
        if (!tooltip) return;
        
        // Create tooltip element if it doesn't exist
        let tooltipEl = document.getElementById('dynamic-tooltip');
        if (!tooltipEl) {
            tooltipEl = document.createElement('div');
            tooltipEl.id = 'dynamic-tooltip';
            tooltipEl.className = 'tooltip-dynamic';
            tooltipEl.style.cssText = `
                position: absolute;
                background: var(--bg-card);
                color: var(--text-primary);
                padding: var(--space-2) var(--space-3);
                border-radius: var(--radius-md);
                font-size: var(--text-xs);
                white-space: nowrap;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.3s ease;
                box-shadow: var(--shadow-lg);
                border: 1px solid var(--border-primary);
                z-index: 1000;
            `;
            document.body.appendChild(tooltipEl);
        }
        
        tooltipEl.textContent = tooltip;
        tooltipEl.style.opacity = '1';
        
        // Position tooltip
        const rect = element.getBoundingClientRect();
        const tooltipRect = tooltipEl.getBoundingClientRect();
        
        tooltipEl.style.left = rect.left + (rect.width - tooltipRect.width) / 2 + 'px';
        tooltipEl.style.top = rect.top - tooltipRect.height - 10 + 'px';
    }
    
    function hideTooltip() {
        const tooltipEl = document.getElementById('dynamic-tooltip');
        if (tooltipEl) {
            tooltipEl.style.opacity = '0';
        }
    }
}

/**
 * Animation Management
 */
function initializeAnimations() {
    // Intersection Observer for scroll animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fadeIn');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe elements that should animate on scroll
    const animatedElements = document.querySelectorAll('.card, .stat-card, .section-card');
    animatedElements.forEach(el => {
        observer.observe(el);
    });
    
    // Add stagger animation to grids
    const grids = document.querySelectorAll('.stats-overview, .action-grid, .modules-grid');
    grids.forEach(grid => {
        const items = grid.children;
        Array.from(items).forEach((item, index) => {
            item.style.animationDelay = `${index * 0.1}s`;
        });
    });
}

/**
 * Accessibility Enhancements
 */
function initializeAccessibility() {
    // Skip to main content link
    const skipLink = document.querySelector('.skip-to-main');
    if (!skipLink) {
        const link = document.createElement('a');
        link.href = '#main-content';
        link.className = 'skip-to-main sr-only';
        link.textContent = 'Skip to main content';
        link.style.cssText = `
            position: absolute;
            top: -40px;
            left: 6px;
            background: var(--accent-primary);
            color: white;
            padding: 8px;
            text-decoration: none;
            border-radius: 4px;
            z-index: 1000;
            transition: top 0.3s;
        `;
        
        link.addEventListener('focus', () => {
            link.style.top = '6px';
            link.classList.remove('sr-only');
        });
        
        link.addEventListener('blur', () => {
            link.style.top = '-40px';
            link.classList.add('sr-only');
        });
        
        document.body.prepend(link);
    }
    
    // Announce page changes to screen readers
    announcePageChange();
    
    // Focus management
    manageFocus();
    
    function announcePageChange() {
        const announcer = document.createElement('div');
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        announcer.className = 'sr-only';
        announcer.id = 'page-announcer';
        document.body.appendChild(announcer);
        
        // Announce current page
        const pageTitle = document.querySelector('.page-title');
        if (pageTitle) {
            announcer.textContent = `Page loaded: ${pageTitle.textContent}`;
        }
    }
    
    function manageFocus() {
        // Focus trap for modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                const modal = document.querySelector('.modal:not([style*="display: none"])');
                if (modal) {
                    trapFocus(e, modal);
                }
            }
        });
        
        function trapFocus(e, container) {
            const focusableElements = container.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];
            
            if (e.shiftKey) {
                if (document.activeElement === firstElement) {
                    lastElement.focus();
                    e.preventDefault();
                }
            } else {
                if (document.activeElement === lastElement) {
                    firstElement.focus();
                    e.preventDefault();
                }
            }
        }
    }
}

/**
 * Utility Functions
 */
const utils = {
    // Debounce function
    debounce(func, wait, immediate) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func.apply(this, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(this, args);
        };
    },
    
    // Throttle function
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    // Format number with commas
    formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    },
    
    // Copy to clipboard
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showToast('Copied to clipboard!', 'success');
            return true;
        } catch (err) {
            console.error('Failed to copy: ', err);
            this.showToast('Failed to copy', 'error');
            return false;
        }
    },
    
    // Show toast notification
    showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--${type === 'success' ? 'success' : type === 'error' ? 'error' : 'info'});
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            z-index: 10000;
            opacity: 0;
            transform: translateX(100%);
            transition: all 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        });
        
        // Remove after duration
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
};

// Global error handler
window.addEventListener('error', (e) => {
    console.error('Global error:', e.error);
    // You could send this to an error reporting service
});

// Export utilities globally
window.appUtils = utils;

// Performance monitoring
if ('PerformanceObserver' in window) {
    const observer = new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
            if (entry.entryType === 'navigation') {
                console.log(`Page load time: ${entry.loadEventEnd - entry.fetchStart}ms`);
            }
        });
    });
    observer.observe({ entryTypes: ['navigation'] });
}