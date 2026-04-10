/**
 * crud-ui.js — Shared CRUD UI components for Tech Process Viewer.
 *
 * Provides: CrudModal, buildForm, getFormData, showNotification, confirm.
 * Uses jQuery (already loaded globally).
 */

(function (window) {
    'use strict';

    // ========== CrudModal ==========

    /**
     * Reusable modal dialog.
     * Creates overlay + modal in DOM on first use.
     *
     * Usage:
     *   var modal = new CrudModal('my-modal');
     *   modal.open('Title', bodyHtml, footerHtml);
     *   modal.close();
     */
    function CrudModal(id) {
        this.id = id;
        this.overlayId = id + '-overlay';
        this._ensureDOM();
    }

    CrudModal.prototype._ensureDOM = function () {
        if (document.getElementById(this.overlayId)) return;

        var html =
            '<div id="' + this.overlayId + '" class="crud-modal-overlay">' +
            '  <div class="crud-modal">' +
            '    <div class="crud-modal-header">' +
            '      <span class="crud-modal-title"></span>' +
            '      <span class="crud-modal-close">&times;</span>' +
            '    </div>' +
            '    <div class="crud-modal-body"></div>' +
            '    <div class="crud-modal-footer"></div>' +
            '  </div>' +
            '</div>';
        document.body.insertAdjacentHTML('beforeend', html);

        var self = this;
        var overlay = document.getElementById(this.overlayId);
        overlay.querySelector('.crud-modal-close').onclick = function () { self.close(); };
        // Close only when both mousedown AND mouseup happen on the overlay background.
        // Prevents accidental close when text selection (Ctrl+C) extends beyond the modal.
        var mouseDownTarget = null;
        overlay.addEventListener('mousedown', function (e) { mouseDownTarget = e.target; });
        overlay.addEventListener('mouseup', function (e) {
            if (mouseDownTarget === overlay && e.target === overlay) self.close();
            mouseDownTarget = null;
        });
    };

    CrudModal.prototype.open = function (title, bodyHtml, footerHtml) {
        var overlay = document.getElementById(this.overlayId);
        overlay.querySelector('.crud-modal-title').textContent = title;
        overlay.querySelector('.crud-modal-body').innerHTML = bodyHtml;
        overlay.querySelector('.crud-modal-footer').innerHTML = footerHtml || '';
        overlay.classList.add('visible');
    };

    CrudModal.prototype.close = function () {
        var overlay = document.getElementById(this.overlayId);
        overlay.classList.remove('visible');
    };

    CrudModal.prototype.getBody = function () {
        return document.getElementById(this.overlayId).querySelector('.crud-modal-body');
    };

    CrudModal.prototype.getFooter = function () {
        return document.getElementById(this.overlayId).querySelector('.crud-modal-footer');
    };

    // ========== Form utilities ==========

    /**
     * Build an HTML form from field definitions.
     *
     * @param {string} formId - ID for the form element
     * @param {Array} fields - [{name, label, type, required, options, value, placeholder}]
     *   type: 'text' | 'number' | 'textarea' | 'select' | 'checkbox' | 'file'
     *   options: [{value, label}] for select type
     * @returns {string} HTML string
     */
    function buildForm(formId, fields) {
        var html = '<form id="' + formId + '" class="crud-form">';

        for (var i = 0; i < fields.length; i++) {
            var f = fields[i];
            var req = f.required ? ' required' : '';
            var val = f.value !== undefined && f.value !== null ? f.value : '';
            var ph = f.placeholder || '';
            var hidden = f.hidden ? ' style="display:none"' : '';

            html += '<div class="form-group"' + hidden + '>';
            if (f.type !== 'checkbox') {
                html += '<label class="form-label" for="' + formId + '-' + f.name + '">' + f.label + '</label>';
            }

            if (f.type === 'textarea') {
                html += '<textarea class="form-input" id="' + formId + '-' + f.name +
                    '" name="' + f.name + '" placeholder="' + ph + '"' + req + '>' + val + '</textarea>';
            } else if (f.type === 'select') {
                html += '<select class="form-select" id="' + formId + '-' + f.name +
                    '" name="' + f.name + '"' + req + '>';
                if (f.options) {
                    for (var j = 0; j < f.options.length; j++) {
                        var opt = f.options[j];
                        var sel = String(opt.value) === String(val) ? ' selected' : '';
                        html += '<option value="' + opt.value + '"' + sel + '>' + opt.label + '</option>';
                    }
                }
                html += '</select>';
            } else if (f.type === 'checkbox') {
                var checked = val ? ' checked' : '';
                html += '<label class="form-checkbox-label">' +
                    '<input type="checkbox" class="form-checkbox" id="' + formId + '-' + f.name +
                    '" name="' + f.name + '"' + checked + '> ' + f.label + '</label>';
            } else if (f.type === 'file') {
                html += '<input type="file" class="form-input" id="' + formId + '-' + f.name +
                    '" name="' + f.name + '"' + req + '>';
            } else {
                html += '<input type="' + (f.type || 'text') + '" class="form-input" id="' +
                    formId + '-' + f.name + '" name="' + f.name +
                    '" value="' + val + '" placeholder="' + ph + '"' + req + '>';
            }

            html += '</div>';
        }

        html += '</form>';
        return html;
    }

    /**
     * Read all form inputs and return an object {name: value}.
     */
    function getFormData(formId) {
        var form = document.getElementById(formId);
        if (!form) return {};
        var data = {};
        var inputs = form.querySelectorAll('input, textarea, select');
        for (var i = 0; i < inputs.length; i++) {
            var el = inputs[i];
            if (el.type === 'checkbox') {
                data[el.name] = el.checked;
            } else if (el.type === 'file') {
                data[el.name] = el.files[0] || null;
            } else if (el.type === 'number') {
                data[el.name] = el.value ? parseFloat(el.value) : 0;
            } else {
                data[el.name] = el.value;
            }
        }
        return data;
    }

    // ========== Notifications ==========

    var notifContainer = null;

    function ensureNotifContainer() {
        if (notifContainer) return;
        notifContainer = document.createElement('div');
        notifContainer.id = 'crud-notifications';
        notifContainer.className = 'crud-notifications';
        document.body.appendChild(notifContainer);
    }

    /**
     * Show a toast notification.
     * @param {string} message
     * @param {'success'|'error'|'info'} type
     */
    function showNotification(message, type) {
        ensureNotifContainer();
        type = type || 'info';
        var div = document.createElement('div');
        div.className = 'notification notification-' + type;
        div.textContent = message;
        notifContainer.appendChild(div);

        setTimeout(function () { div.classList.add('visible'); }, 10);
        setTimeout(function () {
            div.classList.remove('visible');
            setTimeout(function () { div.remove(); }, 300);
        }, 3000);
    }

    // ========== Confirm dialog ==========

    var confirmModal = null;

    /**
     * Show a confirmation dialog.
     * @param {string} message
     * @returns {Promise<boolean>}
     */
    function confirm(message) {
        return new Promise(function (resolve) {
            if (!confirmModal) {
                confirmModal = new CrudModal('crud-confirm');
            }
            var body = '<p class="confirm-message">' + message + '</p>';
            var footer =
                '<button class="btn-crud btn-confirm-ok">OK</button>' +
                '<button class="btn-crud btn-confirm-cancel">Cancel</button>';

            confirmModal.open('Confirmation', body, footer);

            var overlay = document.getElementById('crud-confirm-overlay');
            overlay.querySelector('.btn-confirm-ok').onclick = function () {
                confirmModal.close();
                resolve(true);
            };
            overlay.querySelector('.btn-confirm-cancel').onclick = function () {
                confirmModal.close();
                resolve(false);
            };
        });
    }

    // ========== Toolbar builder ==========

    /**
     * Build a toolbar HTML string.
     * @param {Array} buttons - [{label, className, id, icon}]
     * @returns {string}
     */
    function buildToolbar(buttons) {
        var html = '<div class="toolbar">';
        for (var i = 0; i < buttons.length; i++) {
            var b = buttons[i];
            var cls = b.className || 'btn-crud btn-add';
            var id = b.id ? ' id="' + b.id + '"' : '';
            var icon = b.icon ? b.icon + ' ' : '';
            html += '<button class="' + cls + '"' + id + '>' + icon + b.label + '</button>';
        }
        html += '</div>';
        return html;
    }

    // ========== Export ==========

    window.crudUI = {
        CrudModal: CrudModal,
        buildForm: buildForm,
        getFormData: getFormData,
        showNotification: showNotification,
        confirm: confirm,
        buildToolbar: buildToolbar
    };

})(window);
