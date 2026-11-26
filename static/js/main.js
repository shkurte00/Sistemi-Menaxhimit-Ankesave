let activeComplaintId = null;
let complaintsCache = [];

document.addEventListener('DOMContentLoaded', () => {
    fetchComplaints();

    const form = document.getElementById('complaintForm');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const clientNameInput = document.getElementById('clientName');
            const complaintTypeInput = document.getElementById('complaintType');
            const categoryInput = document.getElementById('category');
            const priorityInput = document.getElementById('priority');
            const descriptionInput = document.getElementById('description');

            const payload = {
                client_name: clientNameInput.value.trim(),
                complaint_type: complaintTypeInput.value,
                category: categoryInput.value,
                priority: priorityInput ? priorityInput.value : 'Mesatare',
                description: descriptionInput.value.trim()
            };

            try {
                const response = await fetch('/api/complaints', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    const result = await response.json();
                    if (result.email_sent) {
                        showNeonNotification("Ankesa u dërgua dhe njoftimi u dërgua në Gmail!", "success");
                    } else {
                        showNeonNotification("Ankesa u ruajt, por njoftimi në Gmail nuk u dërgua!", "error");
                    }
                    form.reset();
                    fetchComplaints();
                } else {
                    const errData = await response.json();
                    console.error('Server error:', errData);
                    showNeonNotification("Gabim gjatë dërgimit të ankesës!", "error");
                }
            } catch (error) {
                console.error('Network error:', error);
                showNeonNotification("Gabim në rrjet!", "error");
            }
        });
    }

    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('#complaintsTableBody tr');

            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }

    const adminSearchInput = document.getElementById('adminSearchInput');
    if (adminSearchInput) {
        adminSearchInput.addEventListener('input', function(e) {
            const term = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('#adminTable tbody tr');
            rows.forEach(row => {
                row.style.display = row.textContent.toLowerCase().includes(term) ? '' : 'none';
            });
        });
    }
});

async function fetchComplaints() {
    try {
        const response = await fetch('/api/complaints');
        if (!response.ok) return;
        const complaints = await response.json();
        complaintsCache = Array.isArray(complaints) ? complaints : [];

        const tbody = document.getElementById('complaintsTableBody');
        if (!tbody) return;

        tbody.innerHTML = '';

        let pendingCount = 0;
        let resolvedCount = 0;

        complaintsCache.forEach((item, index) => {
            const displayNumber = index + 1;
            const clientName = item.full_name || item.client_name || item.clientName || 'N/A';
            const category = item.category_name || item.category || 'N/A';
            const description = item.description || 'N/A';
            const status = item.status || 'Në pritje';

            if (status.toLowerCase().includes('zgjidhur')) {
                resolvedCount++;
            } else {
                pendingCount++;
            }

            const shortText = description.length > 48 ? description.slice(0, 48) + '...' : description;

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="ps-4 fw-semibold text-muted">#${displayNumber}</td>
                <td class="fw-medium text-white">${escapeHtml(clientName)}</td>
                <td><span class="badge badge-client">${escapeHtml(category)}</span></td>
                <td class="text-secondary">
                    <span>${escapeHtml(shortText)}</span>
                    <button type="button" class="btn-see-more ms-2" onclick="openComplaintByIndex(${index})">Shiko më shumë</button>
                </td>
                <td class="text-center pe-4">
                    <span class="${status.toLowerCase().includes('zgjidhur') ? 'text-emerald' : 'text-amber'} fw-semibold">
                        ${escapeHtml(status)}
                    </span>
                </td>
            `;
            tbody.appendChild(tr);
        });

        const statTotal = document.getElementById('totalCount');
        const statPending = document.getElementById('pendingCount');
        const statResolved = document.getElementById('resolvedCount');

        if (statTotal) statTotal.textContent = complaintsCache.length;
        if (statPending) statPending.textContent = pendingCount;
        if (statResolved) statResolved.textContent = resolvedCount;

    } catch (error) {
        console.error('Fetch error:', error);
    }
}

function openComplaintByIndex(index) {
    const item = complaintsCache[index];
    if (!item) return;

    openComplaintPost({
        id: item.id,
        client_name: item.full_name || item.client_name || item.clientName || 'Klient',
        date: item.date || item.created_date || 'Sot',
        time: item.time || item.created_time || '--:--',
        complaint_type: item.complaint_type || 'Online',
        category: item.category_name || item.category || 'Tjetër',
        description: item.description || '',
        admin_comment: item.admin_comment || item.admin_response || ''
    });
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

const adminSearchInput = document.getElementById('adminSearchInput');
if (adminSearchInput) {
    adminSearchInput.addEventListener('input', function(e) {
        const term = e.target.value.toLowerCase();
        const rows = document.querySelectorAll('#adminTable tbody tr');
        rows.forEach(row => {
            row.style.display = row.textContent.toLowerCase().includes(term) ? '' : 'none';
        });
    });
}

function showNeonNotification(message, type = 'success') {
    const existing = document.getElementById('neon-toast-box');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'neon-toast-box';
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background-color: #111827;
        border: 1px solid ${type === 'error' ? '#ef4444' : '#00f3ff'};
        color: #f8fafc;
        padding: 15px 25px;
        border-radius: 10px;
        box-shadow: 0 0 20px ${type === 'error' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(0, 243, 255, 0.3)'};
        z-index: 99999;
        font-size: 0.95rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
        animation: fadeInOut 3s ease forwards;
    `;
    
    toast.innerHTML = `<span>${type === 'error' ? '⚠️' : '✨'}</span> ${escapeHtml(message)}`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function confirmDelete(event, formElement) {
    event.preventDefault(); 

    let modal = document.getElementById('neon-confirm-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'neon-confirm-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(2, 4, 10, 0.8);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 99999;
        `;
        modal.innerHTML = `
            <div style="background: #111827; border: 1px solid rgba(0, 243, 255, 0.4); padding: 25px; border-radius: 14px; width: 350px; text-align: center; box-shadow: 0 0 30px rgba(0,243,255,0.2);">
                <h3 style="color: #00f3ff; margin-bottom: 15px; font-size: 1.1rem;">Konfirmo Veprimin</h3>
                <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 20px;">A jeni të sigurt që dëshironi ta fshini këtë ankesë?</p>
                <div style="display: flex; gap: 10px; justify-content: center;">
                    <button id="neon-cancel-btn" style="background: transparent; border: 1px solid #64748b; color: #f8fafc; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600;">Anulo</button>
                    <button id="neon-ok-btn" style="background: #ef4444; border: none; color: #fff; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600;">Fshi</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    } else {
        modal.style.display = 'flex';
    }

    document.getElementById('neon-ok-btn').onclick = function() {
        modal.style.display = 'none';
        formElement.submit(); 
    };

    document.getElementById('neon-cancel-btn').onclick = function() {
        modal.style.display = 'none';
    };
}

function openComplaintPost(complaintData) {
    activeComplaintId = complaintData.id;

    const postView = document.getElementById('complaintPostView');
    if (!postView) return;

    const clientEl = document.getElementById('postClientName');
    const dateEl = document.getElementById('postDate');
    const timeEl = document.getElementById('postTime');
    const typeEl = document.getElementById('postComplaintType');
    const catEl = document.getElementById('postCategory');
    const descEl = document.getElementById('postDescription');
    const clientCommentBox = document.getElementById('clientAdminCommentBox');
    const clientCommentText = document.getElementById('clientAdminCommentText');

    if (clientEl) clientEl.textContent = complaintData.client_name || 'Klient';
    if (dateEl) dateEl.textContent = complaintData.date || 'Sot';
    if (timeEl) timeEl.textContent = complaintData.time || '--:--';
    if (typeEl) typeEl.textContent = complaintData.complaint_type || 'Online';
    if (catEl) catEl.textContent = complaintData.category || 'Tjetër';
    if (descEl) descEl.textContent = complaintData.description || '';

    if (clientCommentBox && clientCommentText) {
        if (complaintData.admin_comment) {
            clientCommentText.textContent = complaintData.admin_comment;
            clientCommentBox.classList.remove('d-none');
        } else {
            clientCommentText.textContent = '';
            clientCommentBox.classList.add('d-none');
        }
    }

    const commentInput = document.getElementById('adminCommentInput');
    const savedDisplay = document.getElementById('savedCommentDisplay');
    if (commentInput) {
        commentInput.value = complaintData.admin_comment || '';
    }
    if (savedDisplay) {
        savedDisplay.textContent = complaintData.admin_comment
            ? `Komenti aktual: ${complaintData.admin_comment}`
            : '';
    }

    const assignedAdminSelect = document.getElementById('assignedAdminSelect');
    if (assignedAdminSelect) {
        assignedAdminSelect.value = complaintData.assigned_admin_id
            ? String(complaintData.assigned_admin_id)
            : '';
    }
    const dueAtInput = document.getElementById('dueAtInput');
    if (dueAtInput && complaintData.due_at) {
        const due = new Date(complaintData.due_at);
        if (!Number.isNaN(due.getTime())) {
            const local = new Date(due.getTime() - due.getTimezoneOffset() * 60000);
            dueAtInput.value = local.toISOString().slice(0, 16);
        }
    }

    postView.classList.remove('d-none');
    loadComplaintHistory(complaintData.id);
    loadComplaintComments(complaintData.id);
    loadComplaintAttachments(complaintData.id);
    postView.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function loadComplaintComments(complaintId) {
    const list = document.getElementById('complaintCommentsList');
    if (!list) return;
    list.textContent = 'Duke u ngarkuar...';
    try {
        const response = await fetch(`/api/complaints/${complaintId}/comments`);
        if (!response.ok) {
            list.textContent = 'Biseda nuk është e disponueshme.';
            return;
        }
        const comments = await response.json();
        list.innerHTML = comments.length
            ? comments.map(item => `
                <div class="border-bottom border-secondary py-2">
                    <div class="small text-info fw-semibold">${escapeHtml(item.full_name)} · ${escapeHtml(item.role)}</div>
                    <div class="text-light small">${escapeHtml(item.comment)}</div>
                    <div class="text-secondary small">${escapeHtml(item.created_at)}</div>
                </div>
            `).join('')
            : '<div class="text-secondary small">Nuk ka komente ende.</div>';
    } catch (error) {
        list.textContent = 'Gabim në ngarkimin e bisedës.';
    }
}

async function addComplaintComment() {
    if (!activeComplaintId) return;
    const input = document.getElementById('clientCommentInput');
    const comment = input ? input.value.trim() : '';
    if (!comment) {
        showNeonNotification('Shkruani një koment!', 'error');
        return;
    }
    const response = await fetch(`/api/complaints/${activeComplaintId}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment })
    });
    if (response.ok) {
        if (input) input.value = '';
        await loadComplaintComments(activeComplaintId);
        showNeonNotification('Komenti u dërgua!', 'success');
    } else {
        const data = await response.json();
        showNeonNotification(data.error || 'Komenti nuk u dërgua.', 'error');
    }
}

async function loadComplaintAttachments(complaintId) {
    const list = document.getElementById('complaintAttachmentsList');
    if (!list) return;
    list.textContent = 'Duke u ngarkuar...';
    try {
        const response = await fetch(`/api/complaints/${complaintId}/attachments`);
        if (!response.ok) {
            list.textContent = 'Bashkëngjitjet nuk janë të disponueshme.';
            return;
        }
        const attachments = await response.json();
        list.innerHTML = attachments.length
            ? attachments.map(item => `
                <a class="d-block text-info text-decoration-none py-1"
                   href="/api/attachments/${item.id}">${escapeHtml(item.original_name)}</a>
            `).join('')
            : '<div class="text-secondary small">Nuk ka skedarë të bashkëngjitur.</div>';
    } catch (error) {
        list.textContent = 'Gabim në ngarkimin e skedarëve.';
    }
}

async function uploadComplaintAttachment() {
    if (!activeComplaintId) return;
    const input = document.getElementById('complaintAttachmentInput');
    if (!input || !input.files.length) {
        showNeonNotification('Zgjidhni një skedar!', 'error');
        return;
    }
    const formData = new FormData();
    formData.append('file', input.files[0]);
    const response = await fetch(`/api/complaints/${activeComplaintId}/attachments`, {
        method: 'POST',
        body: formData
    });
    if (response.ok) {
        input.value = '';
        await loadComplaintAttachments(activeComplaintId);
        showNeonNotification('Skedari u ngarkua!', 'success');
    } else {
        const data = await response.json();
        showNeonNotification(data.error || 'Ngarkimi dështoi.', 'error');
    }
}

async function updateComplaintAssignment(complaintId) {
    const adminSelect = document.getElementById('assignedAdminSelect');
    const dueInput = document.getElementById('dueAtInput');
    const payload = {
        assigned_admin_id: adminSelect ? adminSelect.value : '',
        due_at: dueInput ? dueInput.value : ''
    };
    const response = await fetch(`/api/complaints/${complaintId}/assignment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (response.ok) {
        showNeonNotification('Caktimi dhe afati u ruajtën!', 'success');
    } else {
        const data = await response.json();
        showNeonNotification(data.error || 'Ruajtja dështoi.', 'error');
    }
}

async function loadComplaintHistory(complaintId) {
    const historyList = document.getElementById('statusHistoryList');
    if (!historyList) return;

    historyList.textContent = 'Duke u ngarkuar...';
    try {
        const response = await fetch(`/api/complaints/${complaintId}/history`);
        if (!response.ok) {
            historyList.textContent = 'Historiku nuk është i disponueshëm.';
            return;
        }
        const history = await response.json();
        if (!Array.isArray(history) || history.length === 0) {
            historyList.textContent = 'Pa ndryshime statusi.';
            return;
        }
        historyList.innerHTML = history.map(item =>
            `<div class="border-bottom border-secondary py-1">
                <span class="text-light">${escapeHtml(item.status)}</span>
                <span class="ms-2">${escapeHtml(item.created_at)}</span>
                <span class="ms-2">nga ${escapeHtml(item.changed_by_name)}</span>
            </div>`
        ).join('');
    } catch (error) {
        historyList.textContent = 'Gabim në ngarkimin e historikut.';
    }
}

function closeComplaintPost() {
    const postView = document.getElementById('complaintPostView');
    if (postView) {
        postView.classList.add('d-none');
    }
}

async function saveAdminComment() {
    if (!activeComplaintId) return;

    const commentInput = document.getElementById('adminCommentInput');
    const comment = commentInput ? commentInput.value.trim() : '';

    try {
        const res = await fetch(`/api/complaints/${activeComplaintId}/comment`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comment })
        });

        if (res.ok) {
            const savedDisplay = document.getElementById('savedCommentDisplay');
            if (savedDisplay) {
                savedDisplay.textContent = comment ? `Komenti aktual: ${comment}` : '';
            }
            showNeonNotification('Komenti u ruajt me sukses!', 'success');
        } else {
            showNeonNotification('Nuk u arrit të ruhet komenti!', 'error');
        }
    } catch (err) {
        showNeonNotification('Gabim në rrjet gjatë ruajtjes së komentit!', 'error');
    }
}

async function updateComplaintStatus(complaintId, status) {
    try {
        const response = await fetch(`/api/complaints/${complaintId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });

        if (response.ok) {
            showNeonNotification('Statusi u përditësua me sukses!', 'success');
        } else {
            const data = await response.json();
            showNeonNotification(data.error || 'Nuk u arrit të përditësohet statusi!', 'error');
            window.location.reload();
        }
    } catch (error) {
        showNeonNotification('Gabim në rrjet gjatë përditësimit!', 'error');
    }
}