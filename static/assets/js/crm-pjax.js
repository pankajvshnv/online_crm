/**
 * CRM Seamless PJAX Navigation Engine (All Menus & Routes)
 * Provides instant, zero-flicker SPA navigation across all CRM pages.
 * Header, Sidebar, Audio Context, Chat Drawer remain permanently mounted while inner .page-content transitions smoothly.
 */
(function () {
    'use strict';

    function cleanPath(pathname) {
        if (!pathname) return '/';
        const cleaned = pathname.replace(/\/$/, '');
        return cleaned === '' ? '/' : cleaned;
    }

    // Excluded paths and patterns from PJAX
    function shouldIgnorePjax(url, link) {
        if (!url || !link) return true;

        if (link.hasAttribute('download') ||
            link.getAttribute('target') === '_blank' ||
            link.hasAttribute('data-no-pjax') ||
            link.getAttribute('data-bs-toggle') === 'modal' ||
            link.getAttribute('data-bs-toggle') === 'collapse' ||
            link.getAttribute('data-bs-toggle') === 'offcanvas') {
            return true;
        }

        if (url.origin !== window.location.origin) return true;

        const p = cleanPath(url.pathname);
        if (p === '/login' ||
            p === '/logout' ||
            p.startsWith('/api/') ||
            p.includes('/export') ||
            p.includes('/download')) {
            return true;
        }

        // Static files or direct file downloads
        if (/\.(xlsx|xls|csv|pdf|zip|gz|sql|png|jpg|jpeg|gif|webp|svg)$/i.test(p)) {
            return true;
        }

        return false;
    }

    // Global DOMContentLoaded & Load execution wrappers
    const _origDocAddEventListener = document.addEventListener;
    document.addEventListener = function (type, listener, options) {
        if (type === 'DOMContentLoaded' && (document.readyState === 'interactive' || document.readyState === 'complete')) {
            setTimeout(listener, 10);
            return;
        }
        return _origDocAddEventListener.call(document, type, listener, options);
    };

    const _origWinAddEventListener = window.addEventListener;
    window.addEventListener = function (type, listener, options) {
        if ((type === 'load' || type === 'pageshow') && document.readyState === 'complete') {
            setTimeout(listener, 10);
            return;
        }
        return _origWinAddEventListener.call(window, type, listener, options);
    };

    // Smooth Top Progress Bar
    let _progressTimer = null;
    function getProgressBar() {
        let bar = document.getElementById('crm-top-progress');
        if (!bar) {
            bar = document.createElement('div');
            bar.id = 'crm-top-progress';
            document.body.appendChild(bar);
        }
        return bar;
    }

    function startProgress() {
        const bar = getProgressBar();
        bar.style.opacity = '1';
        bar.style.width = '30%';
        if (_progressTimer) clearTimeout(_progressTimer);
        _progressTimer = setTimeout(function () {
            if (bar && bar.style.opacity === '1') {
                bar.style.width = '70%';
            }
        }, 150);
    }

    function finishProgress() {
        const bar = getProgressBar();
        if (_progressTimer) clearTimeout(_progressTimer);
        bar.style.width = '100%';
        setTimeout(function () {
            bar.style.opacity = '0';
            setTimeout(function () {
                bar.style.width = '0%';
            }, 250);
        }, 180);
    }

    // Dynamic Sidebar Active State Sync for ALL Menus
    function updateSidebarActive(targetPath) {
        const sideMenu = document.getElementById('side-menu');
        if (!sideMenu) return;

        sideMenu.querySelectorAll('.mm-active').forEach(function (el) {
            el.classList.remove('mm-active');
        });
        sideMenu.querySelectorAll('a.active').forEach(function (el) {
            el.classList.remove('active');
        });

        const cleanTarget = cleanPath(targetPath);

        // 1. Try exact href match
        let link = sideMenu.querySelector('a[href="' + cleanTarget + '"], a[href="' + cleanTarget + '/"]');

        // 2. If not found, try prefix match (for sub-routes like /reports/sales or /settings/users)
        if (!link && cleanTarget !== '/') {
            const links = Array.from(sideMenu.querySelectorAll('a[href]'));
            link = links.find(function (a) {
                const h = cleanPath(a.getAttribute('href'));
                return h !== '/' && (cleanTarget.startsWith(h + '/') || cleanTarget === h);
            });
        }

        if (link) {
            link.classList.add('active');
            const parentLi = link.closest('li');
            if (parentLi) {
                parentLi.classList.add('mm-active');
                const parentSubMenu = parentLi.closest('.sub-menu');
                if (parentSubMenu) {
                    parentSubMenu.classList.add('mm-show');
                    const grandParentLi = parentSubMenu.closest('li');
                    if (grandParentLi) grandParentLi.classList.add('mm-active');
                }
            }
        }
    }

    // Load External Scripts dynamically if not already loaded
    function loadExternalScript(src) {
        return new Promise(function (resolve) {
            if (!src || document.querySelector('script[src="' + src + '"]')) {
                resolve();
                return;
            }
            const s = document.createElement('script');
            s.src = src;
            s.onload = resolve;
            s.onerror = resolve; // Never block page if one external asset fails
            document.body.appendChild(s);
        });
    }

    // Execute Extracted Page Scripts with document.write safety shield
    function executeInlineScripts(container, doc) {
        const scriptsToRun = [];

        // 1. Collect scripts from inside .page-content
        if (container) {
            container.querySelectorAll('script').forEach(function (s) {
                if (!s.src && s.textContent.trim()) {
                    const code = s.textContent.trim();
                    if (!code.includes('document.write') && !scriptsToRun.includes(code)) {
                        scriptsToRun.push(code);
                    }
                }
            });
        }

        // 2. Collect extra_js scripts at the end of doc.body (excluding header/footer/base scripts)
        if (doc && doc.body) {
            doc.body.querySelectorAll('script:not([src])').forEach(function (s) {
                // Ignore scripts inside header, footer, sidebar, or chat drawer
                if (s.closest('header, footer, aside, nav, #crmChatDrawer, #layout-wrapper > header, .footer')) {
                    return;
                }
                if (s.hasAttribute('data-crm-base-script') || s.hasAttribute('data-base-script')) {
                    return;
                }
                const code = s.textContent.trim();
                if (code && !scriptsToRun.includes(code)) {
                    const isBaseScript = code.includes('function resetUserPresenceActivity()') ||
                                         code.includes('window.playChatNotificationSound = function') ||
                                         code.includes('window.showToastNotification = function') ||
                                         code.includes('$.fn.datepicker.defaults.format') ||
                                         code.includes('currentDrawerSelectedUserUuid');
                    if (!isBaseScript) {
                        scriptsToRun.push(code);
                    }
                }
            });
        }

        // 3. Execute with document.write safety shield and ready-event interception
        const _origDocWrite = document.write;
        document.write = function () {
            console.warn('[CRM PJAX] document.write blocked during dynamic page execution');
        };

        const _origDocAddEventListener = document.addEventListener;
        const _origWinAddEventListener = window.addEventListener;
        const deferredReadyCallbacks = [];

        // Intercept DOMContentLoaded and load listeners registered during script execution
        // so that pages expecting DOM ready execute immediately rather than hanging
        document.addEventListener = function (type, listener, options) {
            if ((type === 'DOMContentLoaded' || type === 'load') && typeof listener === 'function') {
                deferredReadyCallbacks.push(listener);
                return;
            }
            return _origDocAddEventListener.call(document, type, listener, options);
        };

        window.addEventListener = function (type, listener, options) {
            if ((type === 'DOMContentLoaded' || type === 'load') && typeof listener === 'function') {
                deferredReadyCallbacks.push(listener);
                return;
            }
            return _origWinAddEventListener.call(window, type, listener, options);
        };

        try {
            scriptsToRun.forEach(function (code) {
                try {
                    // Safe regex to convert top-level let and const to var so scripts can re-execute cleanly on PJAX navigation
                    // Prevents Uncaught SyntaxError: Identifier '...' has already been declared
                    const safeCode = code.replace(/^([ \t]*)(?:let|const)\s+([a-zA-Z0-9_$]+)/gm, '$1var $2');
                    const scriptEl = document.createElement('script');
                    scriptEl.type = 'text/javascript';
                    scriptEl.text = safeCode;
                    document.body.appendChild(scriptEl);
                    document.body.removeChild(scriptEl);
                } catch (err) {
                    console.error('[CRM PJAX] Script execution error:', err);
                }
            });
        } finally {
            document.write = _origDocWrite;
            document.addEventListener = _origDocAddEventListener;
            window.addEventListener = _origWinAddEventListener;
        }

        // Execute all intercepted DOMContentLoaded / load callbacks immediately after scripts are evaluated
        deferredReadyCallbacks.forEach(function (cb) {
            try {
                cb(new Event('DOMContentLoaded'));
            } catch (cbErr) {
                console.error('[CRM PJAX] Error running deferred ready callback:', cbErr);
            }
        });

        // Also fire custom event in case external scripts listen for pjax navigation
        try {
            document.dispatchEvent(new CustomEvent('pjax:contentLoaded', { bubbles: true }));
        } catch (e) {}
    }

    // Core PJAX Page Loader
    let _activeAbortController = null;

    window.loadPjaxPage = function (urlStr, pushHistory) {
        const targetUrl = new URL(urlStr, window.location.origin);
        const targetPath = cleanPath(targetUrl.pathname);

        // Cancel previous pending fetch
        if (_activeAbortController) {
            _activeAbortController.abort();
        }
        _activeAbortController = new AbortController();

        startProgress();
        updateSidebarActive(targetPath);

        // Auto-close mobile sidebar drawer on navigation
        if (window.innerWidth < 992) {
            document.body.classList.remove('sidebar-enable');
        }

        const contentEl = document.querySelector('.main-content .page-content');
        if (contentEl) {
            contentEl.style.transition = 'opacity 0.15s ease';
            contentEl.style.opacity = '0.5';
            contentEl.style.pointerEvents = 'none';
        }

        fetch(urlStr, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-PJAX': 'true'
            },
            signal: _activeAbortController.signal
        })
        .then(function (res) {
            if (!res.ok) {
                window.location.href = urlStr;
                return;
            }
            // Check if server redirected to login or external
            const finalUrl = new URL(res.url, window.location.origin);
            if (shouldIgnorePjax(finalUrl, { getAttribute: function () { return null; }, hasAttribute: function () { return false; } })) {
                window.location.href = res.url;
                return;
            }
            return res.text();
        })
        .then(function (htmlText) {
            if (!htmlText) return;

            const parser = new DOMParser();
            const doc = parser.parseFromString(htmlText, 'text/html');

            const newContent = doc.querySelector('.main-content .page-content');
            if (!newContent || !contentEl) {
                // If page layout doesn't have .page-content, fallback cleanly
                window.location.href = urlStr;
                return;
            }

            // Update document title
            if (doc.title) {
                document.title = doc.title;
            }

            // Collect any external scripts in newContent or extra_js that need loading
            const externalScriptPromises = [];
            doc.querySelectorAll('script[src]').forEach(function (s) {
                const src = s.getAttribute('src');
                if (src && !document.querySelector('script[src="' + src + '"]')) {
                    externalScriptPromises.push(loadExternalScript(src));
                }
            });

            // Swap page content
            contentEl.innerHTML = newContent.innerHTML;
            contentEl.style.opacity = '1';
            contentEl.style.pointerEvents = '';

            // Update browser history
            if (pushHistory) {
                window.history.pushState({ pjax: true, path: targetPath }, doc.title, urlStr);
            }

            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'instant' });

            // Re-render Eva Icons
            if (window.eva && window.eva.replace) {
                try { window.eva.replace(); } catch (e) {}
            }

            // Re-initialize Bootstrap Datepicker if available
            if (window.jQuery && $.fn.datepicker) {
                $('.datepicker').datepicker({
                    format: 'dd/mm/yyyy',
                    autoclose: true,
                    todayHighlight: true
                });
            }

            // Once any external scripts finish loading, run inline scripts
            Promise.all(externalScriptPromises).then(function () {
                executeInlineScripts(contentEl, doc);
                finishProgress();
            });
        })
        .catch(function (err) {
            if (err.name === 'AbortError') return;
            console.warn('[CRM PJAX] Fetch error, falling back to full navigation:', err);
            window.location.href = urlStr;
        });
    };

    // Global Click Interceptor for all internal links
    document.addEventListener('click', function (e) {
        const link = e.target.closest('a[href]');
        if (!link) return;

        const href = link.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) {
            return;
        }

        let targetUrl;
        try {
            targetUrl = new URL(link.href, window.location.origin);
        } catch (err) {
            return;
        }

        if (shouldIgnorePjax(targetUrl, link)) {
            return;
        }

        // If clicking exact current URL, ignore
        if (targetUrl.href === window.location.href) {
            e.preventDefault();
            e.stopImmediatePropagation();
            return;
        }

        e.preventDefault();
        e.stopImmediatePropagation();
        window.loadPjaxPage(targetUrl.href, true);
    });

    // Browser Back / Forward Handling
    window.addEventListener('popstate', function (e) {
        const currentUrl = new URL(window.location.href);
        if (!shouldIgnorePjax(currentUrl, { getAttribute: function () { return null; }, hasAttribute: function () { return false; } })) {
            window.loadPjaxPage(window.location.href, false);
        } else {
            window.location.reload();
        }
    });

    // Mobile Sidebar Drawer Backdrop & Close Handling
    document.addEventListener('click', function (e) {
        if (window.innerWidth >= 992) return;

        // 1. Tapping backdrop closes mobile menu
        if (e.target.closest('#sidebarBackdrop') || e.target.classList.contains('sidebar-backdrop')) {
            document.body.classList.remove('sidebar-enable');
            return;
        }

        // 2. Tapping close button inside mobile menu
        if (e.target.closest('#sidebarMobileCloseBtn')) {
            document.body.classList.remove('sidebar-enable');
            return;
        }

        // 3. Tapping outside when menu is open
        if (document.body.classList.contains('sidebar-enable')) {
            if (!e.target.closest('.sidebar-left') && !e.target.closest('#sidebar-btn')) {
                document.body.classList.remove('sidebar-enable');
            }
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && document.body.classList.contains('sidebar-enable')) {
            document.body.classList.remove('sidebar-enable');
        }
    });

})();
