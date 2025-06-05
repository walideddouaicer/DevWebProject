/**
 * Theme Toggle System
 * Handles dark/light mode switching with localStorage persistence
 */

class ThemeManager {
    constructor() {
        this.currentTheme = 'light';
        this.toggleButton = null;
        this.init();
    }

    init() {
        // Load saved theme or detect system preference
        this.loadTheme();
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.setupToggleButton();
                this.setupSystemThemeListener();
            });
        } else {
            this.setupToggleButton();
            this.setupSystemThemeListener();
        }
    }

    loadTheme() {
        // Check localStorage first
        const savedTheme = localStorage.getItem('theme');
        
        if (savedTheme) {
            this.currentTheme = savedTheme;
        } else {
            // Check system preference
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.currentTheme = prefersDark ? 'dark' : 'light';
        }
        
        this.applyTheme(this.currentTheme, false);
    }

    applyTheme(theme, animate = true) {
        const html = document.documentElement;
        
        // Add transition class for smooth theme change
        if (animate) {
            html.classList.add('theme-transitioning');
        }
        
        // Apply theme
        html.setAttribute('data-theme', theme);
        this.currentTheme = theme;
        
        // Update toggle button if it exists
        this.updateToggleButton();
        
        // Save to localStorage
        localStorage.setItem('theme', theme);
        
        // Remove transition class after animation
        if (animate) {
            setTimeout(() => {
                html.classList.remove('theme-transitioning');
            }, 300);
        }
        
        // Dispatch custom event
        this.dispatchThemeChangeEvent(theme);
    }

    setupToggleButton() {
        // Create toggle button if it doesn't exist
        this.createToggleButton();
        
        // Find existing toggle button
        this.toggleButton = document.getElementById('theme-toggle');
        
        if (this.toggleButton) {
            this.toggleButton.addEventListener('click', () => {
                this.toggleTheme();
            });
            
            // Update button state
            this.updateToggleButton();
        }
    }

    createToggleButton() {
        // Check if button already exists
        if (document.getElementById('theme-toggle')) {
            return;
        }

        // Find the user menu in the top bar
        const userMenu = document.querySelector('.user-menu');
        if (!userMenu) {
            return;
        }

        // Create toggle button
        const toggleButton = document.createElement('button');
        toggleButton.id = 'theme-toggle';
        toggleButton.className = 'theme-toggle';
        toggleButton.setAttribute('aria-label', 'Toggle dark mode');
        toggleButton.setAttribute('title', 'Toggle dark/light mode');
        
        // Create slider
        const slider = document.createElement('div');
        slider.className = 'theme-toggle-slider';
        
        // Create icons
        const sunIcon = document.createElement('i');
        sunIcon.className = 'fas fa-sun theme-toggle-icon';
        sunIcon.style.display = 'block';
        
        const moonIcon = document.createElement('i');
        moonIcon.className = 'fas fa-moon theme-toggle-icon';
        moonIcon.style.display = 'none';
        
        slider.appendChild(sunIcon);
        slider.appendChild(moonIcon);
        toggleButton.appendChild(slider);
        
        // Insert before the first notification button
        const firstNotificationBtn = userMenu.querySelector('.notification-btn');
        if (firstNotificationBtn) {
            userMenu.insertBefore(toggleButton, firstNotificationBtn);
        } else {
            userMenu.prepend(toggleButton);
        }
    }

    updateToggleButton() {
        if (!this.toggleButton) {
            return;
        }
        
        const sunIcon = this.toggleButton.querySelector('.fa-sun');
        const moonIcon = this.toggleButton.querySelector('.fa-moon');
        
        if (this.currentTheme === 'dark') {
            // Show moon icon
            if (sunIcon) {
                sunIcon.style.display = 'none';
                sunIcon.classList.remove('active');
            }
            if (moonIcon) {
                moonIcon.style.display = 'block';
                moonIcon.classList.add('active');
            }
            this.toggleButton.setAttribute('aria-label', 'Switch to light mode');
            this.toggleButton.setAttribute('title', 'Switch to light mode');
        } else {
            // Show sun icon
            if (moonIcon) {
                moonIcon.style.display = 'none';
                moonIcon.classList.remove('active');
            }
            if (sunIcon) {
                sunIcon.style.display = 'block';
                sunIcon.classList.add('active');
            }
            this.toggleButton.setAttribute('aria-label', 'Switch to dark mode');
            this.toggleButton.setAttribute('title', 'Switch to dark mode');
        }
    }

    toggleTheme() {
        const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        this.applyTheme(newTheme, true);
        
        // Add a little haptic feedback if supported
        if ('vibrate' in navigator) {
            navigator.vibrate(50);
        }
        
        // Analytics tracking (optional)
        this.trackThemeChange(newTheme);
    }

    setupSystemThemeListener() {
        // Listen for system theme changes
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        
        mediaQuery.addEventListener('change', (e) => {
            // Only auto-switch if user hasn't manually set a theme
            const savedTheme = localStorage.getItem('theme');
            if (!savedTheme) {
                const newTheme = e.matches ? 'dark' : 'light';
                this.applyTheme(newTheme, true);
            }
        });
    }

    dispatchThemeChangeEvent(theme) {
        const event = new CustomEvent('themeChanged', {
            detail: { theme }
        });
        document.dispatchEvent(event);
    }

    trackThemeChange(theme) {
        // Optional: Send analytics event
        if (typeof gtag !== 'undefined') {
            gtag('event', 'theme_change', {
                'theme': theme,
                'event_category': 'ui_interaction'
            });
        }
        
        // Optional: Console log for debugging
        console.log(`Theme changed to: ${theme}`);
    }

    // Public methods
    getCurrentTheme() {
        return this.currentTheme;
    }

    setTheme(theme) {
        if (theme === 'dark' || theme === 'light') {
            this.applyTheme(theme, true);
        }
    }

    resetTheme() {
        localStorage.removeItem('theme');
        this.loadTheme();
    }
}

// Theme utilities
const themeUtils = {
    // Get system preference
    getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    },
    
    // Check if dark mode is supported
    isDarkModeSupported() {
        return window.matchMedia('(prefers-color-scheme: dark)').media !== 'not all';
    },
    
    // Get theme-aware color
    getThemeColor(lightColor, darkColor) {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        return currentTheme === 'dark' ? darkColor : lightColor;
    },
    
    // Update meta theme-color for mobile browsers
    updateMetaThemeColor() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const metaThemeColor = document.querySelector('meta[name="theme-color"]');
        
        if (metaThemeColor) {
            const color = currentTheme === 'dark' ? '#0f172a' : '#ffffff';
            metaThemeColor.setAttribute('content', color);
        }
    }
};

// Initialize theme manager
const themeManager = new ThemeManager();

// Listen for theme changes to update meta color
document.addEventListener('themeChanged', () => {
    themeUtils.updateMetaThemeColor();
});

// Keyboard shortcut for theme toggle (Ctrl/Cmd + Shift + D)
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'D') {
        e.preventDefault();
        themeManager.toggleTheme();
    }
});

// Export for use in other modules
window.themeManager = themeManager;
window.themeUtils = themeUtils;