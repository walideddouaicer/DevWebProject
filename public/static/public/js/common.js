// Common JavaScript for ENSA Project Manager
// This file handles animations, interactions, and effects across all public pages

class ENSAProjectManager {
    constructor() {
        this.init();
    }

    init() {
        this.setupScrollAnimations();
        this.setupNavbarEffects();
        this.setupCounterAnimations();
        this.setupParallaxEffects();
        this.setupLoadingAnimations();
        this.setupResponsiveMenu();
    }

    // Scroll-triggered animations
    setupScrollAnimations() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // Add animation classes
                    entry.target.classList.add('animate-in');
                    
                    // Apply specific animations based on element type
                    if (entry.target.classList.contains('stat-item')) {
                        this.animateStatItem(entry.target);
                    }
                    
                    if (entry.target.classList.contains('feature-card')) {
                        this.animateFeatureCard(entry.target);
                    }
                    
                    if (entry.target.classList.contains('value-card')) {
                        this.animateValueCard(entry.target);
                    }
                }
            });
        }, observerOptions);

        // Observe elements for animation
        const animatedElements = document.querySelectorAll(`
            .feature-card, .value-card, .project-card, .contact-item, 
            .tech-item, .stat-item, .hero-card, .testimonial-card,
            .mission-text, .story-text, .team-content
        `);

        animatedElements.forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(30px)';
            el.style.transition = 'all 0.6s ease';
            observer.observe(el);
        });
    }

    // Animate individual stat items
    animateStatItem(element) {
        const counter = element.querySelector('[data-count]');
        if (counter) {
            this.animateCounter(counter);
        }
    }

    // Animate feature cards with stagger effect
    animateFeatureCard(element) {
        const delay = Array.from(element.parentNode.children).indexOf(element) * 100;
        setTimeout(() => {
            element.style.opacity = '1';
            element.style.transform = 'translateY(0)';
        }, delay);
    }

    // Animate value cards with rotation effect
    animateValueCard(element) {
        const delay = Array.from(element.parentNode.children).indexOf(element) * 150;
        setTimeout(() => {
            element.style.opacity = '1';
            element.style.transform = 'translateY(0) rotateY(0deg)';
        }, delay);
    }

    // Counter animations
    setupCounterAnimations() {
        this.animatedCounters = new Set();
    }

    animateCounter(counter) {
        if (this.animatedCounters.has(counter)) return;
        this.animatedCounters.add(counter);

        const target = parseInt(counter.getAttribute('data-count'));
        const duration = 2000;
        const increment = target / (duration / 16);
        let current = 0;

        const updateCounter = () => {
            if (current < target) {
                current += increment;
                counter.textContent = Math.floor(current);
                requestAnimationFrame(updateCounter);
            } else {
                counter.textContent = target;
            }
        };

        updateCounter();
    }

    // Navbar scroll effects
    setupNavbarEffects() {
        let lastScrollY = window.scrollY;
        
        window.addEventListener('scroll', () => {
            const navbar = document.querySelector('.navbar');
            const currentScrollY = window.scrollY;
            
            // Background opacity based on scroll
            if (currentScrollY > 100) {
                navbar.style.background = 'rgba(10, 10, 10, 0.95)';
                navbar.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.3)';
                navbar.style.backdropFilter = 'blur(25px)';
            } else {
                navbar.style.background = 'rgba(10, 10, 10, 0.9)';
                navbar.style.boxShadow = 'none';
                navbar.style.backdropFilter = 'blur(20px)';
            }

            // Hide/show navbar on scroll
            if (currentScrollY > lastScrollY && currentScrollY > 200) {
                navbar.style.transform = 'translateY(-100%)';
            } else {
                navbar.style.transform = 'translateY(0)';
            }
            
            lastScrollY = currentScrollY;
        });
    }

    // Parallax effects for hero sections
    setupParallaxEffects() {
        const heroSections = document.querySelectorAll('.hero, .about-hero, .features-hero');
        
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            
            heroSections.forEach(hero => {
                const rate = scrolled * -0.5;
                hero.style.transform = `translateY(${rate}px)`;
            });
        });
    }

    // Loading animations
    setupLoadingAnimations() {
        document.addEventListener('DOMContentLoaded', () => {
            // Fade in body
            document.body.style.opacity = '0';
            setTimeout(() => {
                document.body.style.transition = 'opacity 0.5s ease';
                document.body.style.opacity = '1';
            }, 100);

            // Animate hero elements
            const heroElements = document.querySelectorAll('.hero-text h1, .hero-text p, .hero-buttons');
            heroElements.forEach((el, index) => {
                el.style.opacity = '0';
                el.style.transform = 'translateX(-50px)';
                el.style.transition = 'all 1s ease';
                
                setTimeout(() => {
                    el.style.opacity = '1';
                    el.style.transform = 'translateX(0)';
                }, 200 + (index * 200));
            });

            // Animate hero cards
            const heroCards = document.querySelectorAll('.hero-card');
            heroCards.forEach((card, index) => {
                card.style.opacity = '0';
                card.style.transform = 'translateX(50px)';
                card.style.transition = 'all 1s ease';
                
                setTimeout(() => {
                    card.style.opacity = '1';
                    card.style.transform = 'translateX(0)';
                }, 800 + (index * 100));
            });
        });
    }

    // Responsive menu handling
    setupResponsiveMenu() {
        // Add mobile menu toggle if needed
        const navLinks = document.querySelector('.nav-links');
        const navContainer = document.querySelector('.nav-container');
        
        // Create mobile menu button
        const mobileMenuBtn = document.createElement('button');
        mobileMenuBtn.className = 'mobile-menu-btn';
        mobileMenuBtn.innerHTML = '<i class="fas fa-bars"></i>';
        mobileMenuBtn.style.display = 'none';
        
        // Add styles for mobile menu
        const style = document.createElement('style');
        style.textContent = `
            @media (max-width: 768px) {
                .mobile-menu-btn {
                    display: block !important;
                    background: var(--primary-gradient);
                    border: none;
                    color: white;
                    padding: 0.8rem;
                    border-radius: 8px;
                    font-size: 1.2rem;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }
                
                .mobile-menu-btn:hover {
                    transform: scale(1.1);
                }
                
                .nav-links {
                    position: absolute;
                    top: 100%;
                    left: 0;
                    right: 0;
                    background: rgba(10, 10, 10, 0.95);
                    backdrop-filter: blur(20px);
                    flex-direction: column;
                    padding: 2rem;
                    transform: translateY(-100%);
                    opacity: 0;
                    visibility: hidden;
                    transition: all 0.3s ease;
                }
                
                .nav-links.active {
                    transform: translateY(0);
                    opacity: 1;
                    visibility: visible;
                }
                
                .nav-links a {
                    margin: 0.5rem 0;
                    padding: 1rem;
                    text-align: center;
                    border-radius: 8px;
                    transition: background 0.3s ease;
                }
                
                .nav-links a:hover {
                    background: rgba(102, 126, 234, 0.1);
                }
            }
        `;
        document.head.appendChild(style);
        
        navContainer.appendChild(mobileMenuBtn);
        
        mobileMenuBtn.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            const icon = mobileMenuBtn.querySelector('i');
            if (navLinks.classList.contains('active')) {
                icon.className = 'fas fa-times';
            } else {
                icon.className = 'fas fa-bars';
            }
        });
    }

    // Utility function for smooth scrolling
    smoothScrollTo(target) {
        const element = document.querySelector(target);
        if (element) {
            element.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    }

    // Add hover effects to buttons
    static addButtonEffects() {
        document.querySelectorAll('.btn, .cta-btn, .contact-btn').forEach(btn => {
            btn.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-2px)';
            });
            
            btn.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
        });
    }

    // Add ripple effect to buttons
    static addRippleEffect() {
        document.querySelectorAll('.btn, .cta-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                const ripple = document.createElement('span');
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                ripple.style.cssText = `
                    position: absolute;
                    width: ${size}px;
                    height: ${size}px;
                    left: ${x}px;
                    top: ${y}px;
                    background: rgba(255, 255, 255, 0.3);
                    border-radius: 50%;
                    transform: scale(0);
                    animation: ripple 0.6s ease-out;
                    pointer-events: none;
                `;
                
                this.style.position = 'relative';
                this.style.overflow = 'hidden';
                this.appendChild(ripple);
                
                setTimeout(() => ripple.remove(), 600);
            });
        });
        
        // Add ripple animation
        const rippleStyle = document.createElement('style');
        rippleStyle.textContent = `
            @keyframes ripple {
                to {
                    transform: scale(2);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(rippleStyle);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ENSAProjectManager();
    ENSAProjectManager.addButtonEffects();
    ENSAProjectManager.addRippleEffect();
});

// Export for use in other scripts
window.ENSAProjectManager = ENSAProjectManager;



