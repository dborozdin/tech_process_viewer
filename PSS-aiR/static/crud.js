/**
 * crud.js — CRUD-менеджер для PSS-aiR.
 *
 * Предоставляет модальные окна, формы и операции создания/редактирования/удаления
 * для всех объектов PDM: папки, изделия, BOM, процессы, ресурсы, характеристики, документы.
 *
 * Использует глобальные объекты: bus (EventBus), api (API), toaster (Toaster).
 * Vanilla JS, без зависимостей.
 */

(function (window) {
  'use strict';

  // ========== Утилиты ==========

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function debounce(fn, ms) {
    let t;
    return function () {
      clearTimeout(t);
      const args = arguments, ctx = this;
      t = setTimeout(() => fn.apply(ctx, args), ms);
    };
  }

  // ========== CrudManager ==========

  class CrudManager {
    constructor(bus, api, toaster) {
      this.bus = bus;
      this.api = api;
      this.toaster = toaster;
      this._modalEl = null;
      this._resolveConfirm = null;
    }

    // ---- Модальное окно ----

    _ensureModal() {
      if (this._modalEl) return;
      const html = `
        <div class="modal-overlay" id="crudModalOverlay">
          <div class="modal" style="width:520px;">
            <div class="modal-header">
              <span class="modal-title" id="crudModalTitle"></span>
              <button class="modal-close" id="crudModalClose">&times;</button>
            </div>
            <div class="modal-body" id="crudModalBody"></div>
            <div class="modal-footer" id="crudModalFooter"></div>
          </div>
        </div>`;
      document.body.insertAdjacentHTML('beforeend', html);
      this._modalEl = document.getElementById('crudModalOverlay');
      document.getElementById('crudModalClose').addEventListener('click', () => this.closeModal());
      let mouseDownTarget = null;
      this._modalEl.addEventListener('mousedown', (e) => { mouseDownTarget = e.target; });
      this._modalEl.addEventListener('mouseup', (e) => {
        if (mouseDownTarget === this._modalEl && e.target === this._modalEl) this.closeModal();
        mouseDownTarget = null;
      });
    }

    openModal(title, bodyHtml, footerHtml, width) {
      this._ensureModal();
      document.getElementById('crudModalTitle').textContent = title;
      document.getElementById('crudModalBody').innerHTML = bodyHtml;
      document.getElementById('crudModalFooter').innerHTML = footerHtml || '';
      if (width) this._modalEl.querySelector('.modal').style.width = width;
      else this._modalEl.querySelector('.modal').style.width = '520px';
      this._modalEl.classList.add('visible');
    }

    closeModal() {
      if (this._modalEl) this._modalEl.classList.remove('visible');
      if (this._resolveConfirm) {
        this._resolveConfirm(false);
        this._resolveConfirm = null;
      }
    }

    // ---- Построение форм ----

    /**
     * Генерирует HTML формы.
     * @param {string} formId
     * @param {Array} fields - [{name, label, type, required, options, value, placeholder, hidden}]
     *   type: 'text' | 'number' | 'textarea' | 'select' | 'file' | 'hidden'
     */
    buildForm(formId, fields) {
      let html = `<form id="${formId}" class="crud-form" onsubmit="return false">`;
      for (const f of fields) {
        const req = f.required ? ' required' : '';
        const val = f.value != null ? esc(String(f.value)) : '';
        const ph = f.placeholder ? ` placeholder="${esc(f.placeholder)}"` : '';
        const hidden = f.hidden || f.type === 'hidden' ? ' style="display:none"' : '';
        html += `<div class="form-group"${hidden}>`;
        if (f.type !== 'hidden') {
          html += `<label class="form-label" for="${formId}-${f.name}">${esc(f.label)}</label>`;
        }
        if (f.type === 'textarea') {
          html += `<textarea class="form-input form-textarea" id="${formId}-${f.name}" name="${f.name}"${ph}${req}>${val}</textarea>`;
        } else if (f.type === 'select') {
          html += `<select class="form-input form-select" id="${formId}-${f.name}" name="${f.name}"${req}>`;
          if (f.options) {
            for (const opt of f.options) {
              const sel = String(opt.value) === String(f.value) ? ' selected' : '';
              html += `<option value="${esc(String(opt.value))}"${sel}>${esc(opt.label)}</option>`;
            }
          }
          html += '</select>';
        } else if (f.type === 'file') {
          html += `<input type="file" class="form-input" id="${formId}-${f.name}" name="${f.name}"${req}>`;
        } else if (f.type === 'hidden') {
          html += `<input type="hidden" id="${formId}-${f.name}" name="${f.name}" value="${val}">`;
        } else {
          const t = f.type || 'text';
          const step = t === 'number' ? ' step="any"' : '';
          html += `<input type="${t}" class="form-input" id="${formId}-${f.name}" name="${f.name}" value="${val}"${ph}${step}${req}>`;
        }
        html += '</div>';
      }
      html += '</form>';
      return html;
    }

    /**
     * Считывает данные формы в объект.
     */
    getFormData(formId) {
      const form = document.getElementById(formId);
      if (!form) return {};
      const data = {};
      for (const el of form.querySelectorAll('input, textarea, select')) {
        if (!el.name) continue;
        if (el.type === 'file') data[el.name] = el.files[0] || null;
        else if (el.type === 'number') data[el.name] = el.value !== '' ? parseFloat(el.value) : 0;
        else if (el.type === 'checkbox') data[el.name] = el.checked;
        else data[el.name] = el.value;
      }
      return data;
    }

    /**
     * Диалог подтверждения.
     * @returns {Promise<boolean>}
     */
    confirm(message) {
      return new Promise(resolve => {
        const body = `<p style="padding:8px 0;font-size:14px;">${esc(message)}</p>`;
        const footer =
          `<button class="btn btn-danger" id="crudConfirmOk">Удалить</button>` +
          `<button class="btn btn-secondary" id="crudConfirmCancel">Отмена</button>`;
        this._resolveConfirm = resolve;
        this.openModal('Подтверждение', body, footer);
        document.getElementById('crudConfirmOk').addEventListener('click', () => {
          this._resolveConfirm = null;
          this.closeModal();
          resolve(true);
        });
        document.getElementById('crudConfirmCancel').addEventListener('click', () => {
          this._resolveConfirm = null;
          this.closeModal();
          resolve(false);
        });
      });
    }

    // ---- Хелпер для fetch ----

    async _post(url, body) {
      const resp = await fetch(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      return resp.json();
    }
    async _put(url, body) {
      const resp = await fetch(url, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      return resp.json();
    }
    async _del(url) {
      const resp = await fetch(url, { method: 'DELETE' });
      return resp.json();
    }
    async _get(url) {
      const resp = await fetch(url);
      return resp.json();
    }

    // ========== ПАПКИ ==========

    createFolder(parentId, onSuccess) {
      const fields = [
        { name: 'name', label: 'Наименование папки', type: 'text', required: true, placeholder: 'Введите наименование' },
      ];
      const body = this.buildForm('crudFolderForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudFolderSave">Создать</button>` +
        `<button class="btn btn-secondary" id="crudFolderCancel">Отмена</button>`;
      this.openModal('Создать папку', body, footer);
      document.getElementById('crudFolderCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudFolderSave').addEventListener('click', async () => {
        const data = this.getFormData('crudFolderForm');
        if (!data.name.trim()) return;
        try {
          const result = await this._post('/api/folders', { name: data.name, parent_id: parentId });
          if (result.sys_id || result.error == null) {
            this.toaster.show('Папка создана', 'success');
            this.closeModal();
            if (onSuccess) onSuccess(result);
          } else {
            this.toaster.show(result.error || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    renameFolder(folderId, currentName, onSuccess) {
      const fields = [
        { name: 'name', label: 'Наименование', type: 'text', required: true, value: currentName },
      ];
      const body = this.buildForm('crudRenameFolderForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudRenameSave">Сохранить</button>` +
        `<button class="btn btn-secondary" id="crudRenameCancel">Отмена</button>`;
      this.openModal('Переименовать папку', body, footer);
      document.getElementById('crudRenameCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudRenameSave').addEventListener('click', async () => {
        const data = this.getFormData('crudRenameFolderForm');
        if (!data.name.trim()) return;
        try {
          const result = await this._put(`/api/crud/folders/${folderId}`, { name: data.name });
          if (result.success) {
            this.toaster.show('Папка переименована', 'success');
            this.closeModal();
            if (onSuccess) onSuccess();
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    async deleteFolder(folderId, folderName, onSuccess) {
      const ok = await this.confirm(`Удалить папку "${folderName}"?`);
      if (!ok) return;
      try {
        const result = await this._del(`/api/crud/folders/${folderId}`);
        if (result.success) {
          this.toaster.show('Папка удалена', 'success');
          if (onSuccess) onSuccess();
        } else {
          this.toaster.show(result.message || 'Ошибка', 'error');
        }
      } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
    }

    // ========== ИЗДЕЛИЯ ==========

    _productFields(data) {
      return [
        { name: 'id', label: 'Обозначение', type: 'text', required: true, value: data.id || data.designation || '' },
        { name: 'name', label: 'Наименование', type: 'text', required: true, value: data.name || '' },
        { name: 'code1', label: 'Код 1', type: 'text', value: data.code1 || '' },
        { name: 'code2', label: 'Код 2', type: 'text', value: data.code2 || '' },
        { name: 'formation_type', label: 'Тип', type: 'select', value: data.formation_type || 'part', options: [
          { value: 'part', label: 'Деталь' },
          { value: 'assembly', label: 'Сборка' },
          { value: 'material', label: 'Материал' },
          { value: 'kit', label: 'Комплект' },
          { value: 'komplex', label: 'Комплекс' },
        ]},
        { name: 'make_or_buy', label: 'Источник', type: 'select', value: data.make_or_buy || 'make', options: [
          { value: 'make', label: 'Изготовление' },
          { value: 'buy', label: 'Покупное' },
          { value: 'not_known', label: 'Не известно' },
        ]},
        { name: 'description', label: 'Описание', type: 'textarea', value: data.description || '' },
      ];
    }

    /**
     * Создать изделие.
     * @param {number|null} folderId - папка для добавления
     * @param {function} onSuccess - callback
     * @param {object|null} parentInfo - {pdf_id, designation, name} вышестоящего изделия (для BOM)
     */
    createProduct(folderId, onSuccess, parentInfo) {
      const fields = this._productFields({});
      // Добавить поля BOM если есть вышестоящее изделие
      if (parentInfo) {
        fields.push(
          { name: 'quantity', label: 'Количество', type: 'number', value: 1, required: true },
          { name: 'reference_designator', label: 'Позиционное обозначение', type: 'text' }
        );
      }
      let body = '';
      if (parentInfo) {
        const pLabel = esc(parentInfo.designation || '') + (parentInfo.name ? ': ' + esc(parentInfo.name) : '');
        body += `<div style="padding:8px 12px;margin-bottom:12px;background:#e0f4f4;border-left:3px solid #005566;border-radius:4px;font-size:13px;">` +
          `Вхождение в состав: <strong>${pLabel}</strong></div>`;
      }
      body += this.buildForm('crudProductForm', fields);
      const title = parentInfo ? 'Создать изделие и включить в состав' : 'Создать изделие';
      const footer =
        `<button class="btn btn-primary" id="crudProductSave">Создать</button>` +
        `<button class="btn btn-secondary" id="crudProductCancel">Отмена</button>`;
      this.openModal(title, body, footer);
      document.getElementById('crudProductCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudProductSave').addEventListener('click', async () => {
        const data = this.getFormData('crudProductForm');
        if (!data.id.trim() || !data.name.trim()) {
          this.toaster.show('Обозначение и наименование обязательны', 'warning');
          return;
        }
        data.folder_id = folderId;
        if (parentInfo) {
          data.parent_pdf_id = parentInfo.pdf_id;
        }
        try {
          const result = await this._post('/api/crud/products', data);
          if (result.success) {
            this.toaster.show('Изделие создано', 'success');
            this.closeModal();
            if (onSuccess) onSuccess(result.data);
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    editProduct(pdfId, currentData, onSuccess) {
      const fields = this._productFields(currentData);
      const body = this.buildForm('crudProductEditForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudProductEditSave">Сохранить</button>` +
        `<button class="btn btn-secondary" id="crudProductEditCancel">Отмена</button>`;
      this.openModal('Редактировать изделие', body, footer);
      document.getElementById('crudProductEditCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudProductEditSave').addEventListener('click', async () => {
        const data = this.getFormData('crudProductEditForm');
        try {
          const result = await this._put(`/api/crud/products/${pdfId}`, data);
          if (result.success) {
            this.toaster.show('Изделие обновлено', 'success');
            this.closeModal();
            if (onSuccess) onSuccess();
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    async deleteProduct(pdfId, productName, folderId, onSuccess) {
      const ok = await this.confirm(`Удалить изделие "${productName}"?`);
      if (!ok) return;
      try {
        const url = folderId ? `/api/crud/products/${pdfId}?folder_id=${folderId}` : `/api/crud/products/${pdfId}`;
        const result = await this._del(url);
        if (result.success) {
          this.toaster.show('Изделие удалено', 'success');
          if (onSuccess) onSuccess();
        } else {
          this.toaster.show(result.message || 'Ошибка', 'error');
        }
      } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
    }

    // ========== BOM (Состав изделия) ==========

    addBomComponent(parentPdfId, onSuccess) {
      const fields = [
        { name: 'search', label: 'Поиск изделия', type: 'text', placeholder: 'Введите обозначение или наименование...' },
        { name: 'child_pdf_id', label: '', type: 'hidden', value: '' },
        { name: 'quantity', label: 'Количество', type: 'number', value: 1, required: true },
        { name: 'reference_designator', label: 'Позиционное обозначение', type: 'text' },
      ];
      let body = this.buildForm('crudBomForm', fields);
      body += '<div id="crudBomSearchResults" class="search-results" style="display:none"></div>';
      const footer =
        `<button class="btn btn-primary" id="crudBomSave" disabled>Добавить</button>` +
        `<button class="btn btn-secondary" id="crudBomCancel">Отмена</button>`;
      this.openModal('Добавить компонент', body, footer);

      const searchInput = document.getElementById('crudBomForm-search');
      const hiddenInput = document.getElementById('crudBomForm-child_pdf_id');
      const resultsDiv = document.getElementById('crudBomSearchResults');
      const saveBtn = document.getElementById('crudBomSave');

      // Поиск с debounce
      const doSearch = debounce(async () => {
        const q = searchInput.value.trim();
        if (q.length < 2) { resultsDiv.style.display = 'none'; return; }
        try {
          const results = await this.api.productSearch(q);
          if (!results || !results.length) {
            resultsDiv.innerHTML = '<div class="search-result-item" style="color:#999">Ничего не найдено</div>';
            resultsDiv.style.display = 'block';
            return;
          }
          resultsDiv.innerHTML = results.slice(0, 15).map(r => {
            const attrs = r.attributes || r;
            const name = attrs.name || '';
            const id = attrs.id || attrs.product_id || '';
            const sysId = r.sys_id || r.id;
            return `<div class="search-result-item" data-id="${sysId}" data-name="${esc(name)}" data-designation="${esc(id)}">${esc(id)} — ${esc(name)}</div>`;
          }).join('');
          resultsDiv.style.display = 'block';
          resultsDiv.querySelectorAll('.search-result-item[data-id]').forEach(item => {
            item.addEventListener('click', () => {
              hiddenInput.value = item.dataset.id;
              searchInput.value = `${item.dataset.designation} — ${item.dataset.name}`;
              resultsDiv.style.display = 'none';
              saveBtn.disabled = false;
            });
          });
        } catch (e) { /* ignore */ }
      }, 300);
      searchInput.addEventListener('input', doSearch);

      document.getElementById('crudBomCancel').addEventListener('click', () => this.closeModal());
      saveBtn.addEventListener('click', async () => {
        const data = this.getFormData('crudBomForm');
        if (!data.child_pdf_id) {
          this.toaster.show('Выберите изделие из списка поиска', 'warning');
          return;
        }
        try {
          const result = await this._post(`/api/crud/products/${parentPdfId}/bom`, data);
          if (result.success) {
            this.toaster.show('Компонент добавлен', 'success');
            this.closeModal();
            if (onSuccess) onSuccess(result.data);
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    editBomLink(bomId, currentData, onSuccess) {
      const fields = [
        { name: 'quantity', label: 'Количество', type: 'number', value: currentData.quantity || 1, required: true },
        { name: 'reference_designator', label: 'Позиционное обозначение', type: 'text', value: currentData.reference_designator || '' },
      ];
      const body = this.buildForm('crudBomEditForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudBomEditSave">Сохранить</button>` +
        `<button class="btn btn-secondary" id="crudBomEditCancel">Отмена</button>`;
      this.openModal('Редактировать связь', body, footer);
      document.getElementById('crudBomEditCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudBomEditSave').addEventListener('click', async () => {
        const data = this.getFormData('crudBomEditForm');
        try {
          const result = await this._put(`/api/crud/bom/${bomId}`, data);
          if (result.success) {
            this.toaster.show('Связь обновлена', 'success');
            this.closeModal();
            if (onSuccess) onSuccess();
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    async deleteBomLink(bomId, componentName, onSuccess) {
      const ok = await this.confirm(`Удалить компонент "${componentName}" из состава?`);
      if (!ok) return;
      try {
        const result = await this._del(`/api/crud/bom/${bomId}`);
        if (result.success) {
          this.toaster.show('Компонент удалён', 'success');
          if (onSuccess) onSuccess();
        } else {
          this.toaster.show(result.message || 'Ошибка', 'error');
        }
      } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
    }

    // ========== БИЗНЕС-ПРОЦЕССЫ ==========

    _processFields(data) {
      return [
        { name: 'id', label: 'Обозначение', type: 'text', value: data.id || '' },
        { name: 'name', label: 'Наименование', type: 'text', required: true, value: data.name || '' },
        { name: 'type_name', label: 'Тип процесса', type: 'text', value: data.type_name || '' },
        { name: 'description', label: 'Описание', type: 'textarea', value: data.description || '' },
      ];
    }

    createProcess(pdfId, onSuccess) {
      const fields = this._processFields({});
      const body = this.buildForm('crudProcessForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudProcessSave">Создать</button>` +
        `<button class="btn btn-secondary" id="crudProcessCancel">Отмена</button>`;
      this.openModal('Создать процесс', body, footer);
      document.getElementById('crudProcessCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudProcessSave').addEventListener('click', async () => {
        const data = this.getFormData('crudProcessForm');
        if (!data.name.trim()) {
          this.toaster.show('Наименование обязательно', 'warning');
          return;
        }
        if (pdfId) data.pdf_id = pdfId;
        try {
          const result = await this._post('/api/crud/processes', data);
          if (result.success) {
            this.toaster.show('Процесс создан', 'success');
            this.closeModal();
            if (onSuccess) onSuccess(result.data);
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    editProcess(bpId, currentData, onSuccess) {
      const fields = this._processFields(currentData);
      const body = this.buildForm('crudProcessEditForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudProcessEditSave">Сохранить</button>` +
        `<button class="btn btn-secondary" id="crudProcessEditCancel">Отмена</button>`;
      this.openModal('Редактировать процесс', body, footer);
      document.getElementById('crudProcessEditCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudProcessEditSave').addEventListener('click', async () => {
        const data = this.getFormData('crudProcessEditForm');
        try {
          const result = await this._put(`/api/crud/processes/${bpId}`, data);
          if (result.success) {
            this.toaster.show('Процесс обновлён', 'success');
            this.closeModal();
            if (onSuccess) onSuccess();
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    async deleteProcess(bpId, processName, onSuccess) {
      const ok = await this.confirm(`Удалить процесс "${processName}"?`);
      if (!ok) return;
      try {
        const result = await this._del(`/api/crud/processes/${bpId}`);
        if (result.success) {
          this.toaster.show('Процесс удалён', 'success');
          if (onSuccess) onSuccess();
        } else {
          this.toaster.show(result.message || 'Ошибка', 'error');
        }
      } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
    }

    // ========== РЕСУРСЫ ==========

    async addResource(processId, onSuccess) {
      // Загрузить типы ресурсов
      let types = [];
      try {
        const resp = await this._get('/api/crud/resource-types');
        types = (resp.data || []).map(t => ({ value: t.sys_id, label: t.name || t.id }));
      } catch (e) { /* ignore */ }

      const fields = [
        { name: 'type_id', label: 'Тип ресурса', type: 'select', required: true, options: types },
        { name: 'name', label: 'Наименование', type: 'text', required: true },
        { name: 'id', label: 'Обозначение', type: 'text' },
        { name: 'value_component', label: 'Значение', type: 'number', value: 0 },
      ];
      const body = this.buildForm('crudResourceForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudResourceSave">Создать</button>` +
        `<button class="btn btn-secondary" id="crudResourceCancel">Отмена</button>`;
      this.openModal('Добавить ресурс', body, footer);
      document.getElementById('crudResourceCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudResourceSave').addEventListener('click', async () => {
        const data = this.getFormData('crudResourceForm');
        data.process_id = processId;
        try {
          const result = await this._post('/api/crud/resources', data);
          if (result.success) {
            this.toaster.show('Ресурс создан', 'success');
            this.closeModal();
            if (onSuccess) onSuccess(result.data);
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    editResource(resourceId, currentData, onSuccess) {
      const fields = [
        { name: 'name', label: 'Наименование', type: 'text', required: true, value: currentData.name || '' },
        { name: 'value_component', label: 'Значение', type: 'number', value: currentData.value || 0 },
      ];
      const body = this.buildForm('crudResourceEditForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudResourceEditSave">Сохранить</button>` +
        `<button class="btn btn-secondary" id="crudResourceEditCancel">Отмена</button>`;
      this.openModal('Редактировать ресурс', body, footer);
      document.getElementById('crudResourceEditCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudResourceEditSave').addEventListener('click', async () => {
        const data = this.getFormData('crudResourceEditForm');
        try {
          const result = await this._put(`/api/crud/resources/${resourceId}`, data);
          if (result.success) {
            this.toaster.show('Ресурс обновлён', 'success');
            this.closeModal();
            if (onSuccess) onSuccess();
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    async deleteResource(resourceId, resourceName, onSuccess) {
      const ok = await this.confirm(`Удалить ресурс "${resourceName}"?`);
      if (!ok) return;
      try {
        const result = await this._del(`/api/crud/resources/${resourceId}`);
        if (result.success) {
          this.toaster.show('Ресурс удалён', 'success');
          if (onSuccess) onSuccess();
        } else {
          this.toaster.show(result.message || 'Ошибка', 'error');
        }
      } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
    }

    // ========== ХАРАКТЕРИСТИКИ ==========

    async addCharacteristic(itemId, onSuccess) {
      let chars = [];
      try {
        const resp = await this._get('/api/crud/characteristics');
        chars = (resp.data || []).map(c => ({ value: c.sys_id, label: c.name || c.id }));
      } catch (e) { /* ignore */ }

      const fields = [
        { name: 'characteristic_id', label: 'Характеристика', type: 'select', required: true, options: chars },
        { name: 'value', label: 'Значение', type: 'text', required: true },
      ];
      const body = this.buildForm('crudCharForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudCharSave">Создать</button>` +
        `<button class="btn btn-secondary" id="crudCharCancel">Отмена</button>`;
      this.openModal('Добавить характеристику', body, footer);
      document.getElementById('crudCharCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudCharSave').addEventListener('click', async () => {
        const data = this.getFormData('crudCharForm');
        data.item_id = itemId;
        try {
          const result = await this._post('/api/crud/characteristics/values', data);
          if (result.success) {
            this.toaster.show('Характеристика добавлена', 'success');
            this.closeModal();
            if (onSuccess) onSuccess(result.data);
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    editCharacteristic(valueId, currentData, onSuccess) {
      const fields = [
        { name: 'value', label: 'Значение', type: 'text', required: true, value: currentData.value || '' },
      ];
      const body = this.buildForm('crudCharEditForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudCharEditSave">Сохранить</button>` +
        `<button class="btn btn-secondary" id="crudCharEditCancel">Отмена</button>`;
      this.openModal('Редактировать характеристику', body, footer);
      document.getElementById('crudCharEditCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudCharEditSave').addEventListener('click', async () => {
        const data = this.getFormData('crudCharEditForm');
        data.subtype = currentData.subtype || 'apl_descriptive_characteristic_value';
        try {
          const result = await this._put(`/api/crud/characteristics/values/${valueId}`, data);
          if (result.success) {
            this.toaster.show('Характеристика обновлена', 'success');
            this.closeModal();
            if (onSuccess) onSuccess();
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    async deleteCharacteristic(valueId, charName, onSuccess) {
      const ok = await this.confirm(`Удалить характеристику "${charName}"?`);
      if (!ok) return;
      try {
        const result = await this._del(`/api/crud/characteristics/values/${valueId}`);
        if (result.success) {
          this.toaster.show('Характеристика удалена', 'success');
          if (onSuccess) onSuccess();
        } else {
          this.toaster.show(result.message || 'Ошибка', 'error');
        }
      } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
    }

    // ========== ДОКУМЕНТЫ ==========

    attachDocument(itemId, itemType, onSuccess) {
      const fields = [
        { name: 'search', label: 'Поиск документа по коду', type: 'text', placeholder: 'Введите код документа...' },
        { name: 'doc_id', label: '', type: 'hidden', value: '' },
      ];
      let body = this.buildForm('crudDocAttachForm', fields);
      body += '<div id="crudDocSearchResults" class="search-results" style="display:none"></div>';
      const footer =
        `<button class="btn btn-primary" id="crudDocAttachSave" disabled>Привязать</button>` +
        `<button class="btn btn-secondary" id="crudDocAttachCancel">Отмена</button>`;
      this.openModal('Привязать документ', body, footer);

      const searchInput = document.getElementById('crudDocAttachForm-search');
      const hiddenInput = document.getElementById('crudDocAttachForm-doc_id');
      const resultsDiv = document.getElementById('crudDocSearchResults');
      const saveBtn = document.getElementById('crudDocAttachSave');

      const doSearch = debounce(async () => {
        const q = searchInput.value.trim();
        if (q.length < 2) { resultsDiv.style.display = 'none'; return; }
        try {
          const resp = await this._get(`/api/crud/documents/search?q=${encodeURIComponent(q)}`);
          const docs = resp.data || [];
          if (!docs.length) {
            resultsDiv.innerHTML = '<div class="search-result-item" style="color:#999">Ничего не найдено</div>';
            resultsDiv.style.display = 'block';
            return;
          }
          resultsDiv.innerHTML = docs.map(d =>
            `<div class="search-result-item" data-id="${d.sys_id}" data-name="${esc(d.name)}">${esc(d.doc_id)} — ${esc(d.name)}</div>`
          ).join('');
          resultsDiv.style.display = 'block';
          resultsDiv.querySelectorAll('.search-result-item[data-id]').forEach(item => {
            item.addEventListener('click', () => {
              hiddenInput.value = item.dataset.id;
              searchInput.value = item.textContent;
              resultsDiv.style.display = 'none';
              saveBtn.disabled = false;
            });
          });
        } catch (e) { /* ignore */ }
      }, 300);
      searchInput.addEventListener('input', doSearch);

      document.getElementById('crudDocAttachCancel').addEventListener('click', () => this.closeModal());
      saveBtn.addEventListener('click', async () => {
        const data = this.getFormData('crudDocAttachForm');
        if (!data.doc_id) {
          this.toaster.show('Выберите документ из списка', 'warning');
          return;
        }
        try {
          const result = await this._post('/api/crud/documents/attach', {
            doc_id: parseInt(data.doc_id), item_id: itemId, item_type: itemType
          });
          if (result.success) {
            this.toaster.show('Документ привязан', 'success');
            this.closeModal();
            if (onSuccess) onSuccess(result.data);
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    uploadDocument(itemId, itemType, onSuccess) {
      const fields = [
        { name: 'file', label: 'Файл', type: 'file', required: true },
        { name: 'doc_id', label: 'Код документа', type: 'text', placeholder: 'Оставьте пустым — имя файла' },
        { name: 'doc_name', label: 'Наименование', type: 'text', placeholder: 'Оставьте пустым — имя файла' },
      ];
      const body = this.buildForm('crudDocUploadForm', fields);
      const footer =
        `<button class="btn btn-primary" id="crudDocUploadSave">Загрузить</button>` +
        `<button class="btn btn-secondary" id="crudDocUploadCancel">Отмена</button>`;
      this.openModal('Загрузить документ', body, footer);
      document.getElementById('crudDocUploadCancel').addEventListener('click', () => this.closeModal());
      document.getElementById('crudDocUploadSave').addEventListener('click', async () => {
        const fileInput = document.getElementById('crudDocUploadForm-file');
        const file = fileInput.files[0];
        if (!file) {
          this.toaster.show('Выберите файл', 'warning');
          return;
        }
        const formData = new FormData();
        formData.append('file', file);
        const docId = document.getElementById('crudDocUploadForm-doc_id').value;
        const docName = document.getElementById('crudDocUploadForm-doc_name').value;
        if (docId) formData.append('doc_id', docId);
        if (docName) formData.append('doc_name', docName);
        if (itemId) formData.append('item_id', String(itemId));
        if (itemType) formData.append('item_type', itemType);
        try {
          const resp = await fetch('/api/crud/documents/upload', { method: 'POST', body: formData });
          const result = await resp.json();
          if (result.success) {
            this.toaster.show('Документ загружен', 'success');
            this.closeModal();
            if (onSuccess) onSuccess(result.data);
          } else {
            this.toaster.show(result.message || 'Ошибка', 'error');
          }
        } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
      });
    }

    async detachDocument(refId, docName, onSuccess) {
      const ok = await this.confirm(`Отвязать документ "${docName}"?`);
      if (!ok) return;
      try {
        const result = await this._del(`/api/crud/documents/detach/${refId}`);
        if (result.success) {
          this.toaster.show('Документ отвязан', 'success');
          if (onSuccess) onSuccess();
        } else {
          this.toaster.show(result.message || 'Ошибка', 'error');
        }
      } catch (e) { this.toaster.show('Ошибка: ' + e.message, 'error'); }
    }
  }

  window.CrudManager = CrudManager;
})(window);
