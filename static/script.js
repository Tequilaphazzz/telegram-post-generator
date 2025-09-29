// Глобальные переменные для отслеживания одобрения
let approvals = {
    text: false,
    image: false,
    headline: false
};

// Загрузка конфигурации при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    loadConfig();
});

// Загрузка сохраненной конфигурации
async function loadConfig() {
    try {
        const response = await fetch('/get_config');
        const data = await response.json();
        
        if (data.status === 'success' && data.config) {
            // Заполняем поля формы
            for (const [key, value] of Object.entries(data.config)) {
                const element = document.getElementById(key);
                if (element) {
                    element.value = value || '';
                }
            }
        }
    } catch (error) {
        console.error('Ошибка загрузки конфигурации:', error);
    }
}

// Сохранение конфигурации
document.getElementById('configForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = {
        openai_key: document.getElementById('openai_key').value,
        stability_key: document.getElementById('stability_key').value,
        telegram_api_id: document.getElementById('telegram_api_id').value,
        telegram_api_hash: document.getElementById('telegram_api_hash').value,
        telegram_phone: document.getElementById('telegram_phone').value,
        telegram_group: document.getElementById('telegram_group').value
    };
    
    showLoader();
    
    try {
        const response = await fetch('/save_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showMessage('success', '✅ Конфигурация сохранена успешно!');
        } else {
            showMessage('danger', `❌ Ошибка: ${data.message}`);
        }
    } catch (error) {
        showMessage('danger', `❌ Ошибка сохранения: ${error.message}`);
    } finally {
        hideLoader();
    }
});

// Генерация контента
document.getElementById('generateForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const topic = document.getElementById('topic').value;
    
    if (!topic) {
        showMessage('warning', '⚠️ Пожалуйста, введите тему поста');
        return;
    }
    
    // Сброс одобрений
    resetApprovals();
    
    showLoader();
    showMessage('info', '🔄 Генерация контента... Это может занять несколько минут.');
    
    try {
        const response = await fetch('/generate_content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ topic })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Отображаем предпросмотр
            displayPreview(data.data);
            showMessage('success', '✅ Контент успешно сгенерирован!');
        } else {
            showMessage('danger', `❌ Ошибка генерации: ${data.message}`);
        }
    } catch (error) {
        showMessage('danger', `❌ Ошибка: ${error.message}`);
    } finally {
        hideLoader();
    }
});

// Отображение предпросмотра
function displayPreview(data) {
    document.getElementById('postTextPreview').textContent = data.text;
    document.getElementById('imagePreview').src = data.image;
    document.getElementById('headlinePreview').textContent = data.headline;
    
    document.getElementById('previewCard').style.display = 'block';
    
    // Прокрутка к предпросмотру
    document.getElementById('previewCard').scrollIntoView({ behavior: 'smooth' });
}

// Регенерация контента
async function regenerateContent(type) {
    showLoader();
    showMessage('info', `🔄 Регенерация ${getTypeName(type)}...`);
    
    try {
        const response = await fetch('/regenerate_content', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ type })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Обновляем соответствующую часть
            if (type === 'text') {
                document.getElementById('postTextPreview').textContent = data.data.text;
                approvals.text = false;
            } else if (type === 'image') {
                document.getElementById('imagePreview').src = data.data.image;
                approvals.image = false;
            } else if (type === 'headline') {
                document.getElementById('headlinePreview').textContent = data.data.headline;
                document.getElementById('imagePreview').src = data.data.image;
                approvals.headline = false;
            }
            
            updateApprovalStatus();
            showMessage('success', `✅ ${getTypeName(type)} успешно обновлен!`);
        } else {
            showMessage('danger', `❌ Ошибка регенерации: ${data.message}`);
        }
    } catch (error) {
        showMessage('danger', `❌ Ошибка: ${error.message}`);
    } finally {
        hideLoader();
    }
}

// Одобрение контента
function approveContent(type) {
    approvals[type] = true;
    updateApprovalStatus();
    showMessage('success', `✅ ${getTypeName(type)} одобрен!`);
}

// Обновление статуса одобрения
function updateApprovalStatus() {
    // Обновляем бейджи
    updateBadge('textApproval', approvals.text);
    updateBadge('imageApproval', approvals.image);
    updateBadge('headlineApproval', approvals.headline);
    
    // Активируем кнопку публикации если все одобрено
    const publishBtn = document.getElementById('publishBtn');
    if (approvals.text && approvals.image && approvals.headline) {
        publishBtn.disabled = false;
        publishBtn.classList.add('btn-success');
        publishBtn.classList.remove('btn-primary');
    } else {
        publishBtn.disabled = true;
        publishBtn.classList.add('btn-primary');
        publishBtn.classList.remove('btn-success');
    }
}

// Обновление бейджа
function updateBadge(elementId, approved) {
    const badge = document.getElementById(elementId);
    if (approved) {
        badge.textContent = 'Одобрено';
        badge.className = 'badge bg-success';
    } else {
        badge.textContent = 'Ожидает';
        badge.className = 'badge bg-secondary';
    }
}

// Сброс одобрений
function resetApprovals() {
    approvals = {
        text: false,
        image: false,
        headline: false
    };
    updateApprovalStatus();
}

// Публикация поста
async function publishPost() {
    if (!approvals.text || !approvals.image || !approvals.headline) {
        showMessage('warning', '⚠️ Пожалуйста, одобрите все элементы перед публикацией');
        return;
    }
    
    showLoader();
    showMessage('info', '📤 Публикация в Telegram...');
    
    try {
        const response = await fetch('/publish_post', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showMessage('success', '🎉 Пост успешно опубликован в Telegram!');
            // Очищаем форму и предпросмотр
            document.getElementById('topic').value = '';
            document.getElementById('previewCard').style.display = 'none';
            resetApprovals();
        } else {
            if (data.message.includes('верификация')) {
                // Показываем модальное окно для ввода кода
                const modal = new bootstrap.Modal(document.getElementById('telegramCodeModal'));
                modal.show();
            } else {
                showMessage('danger', `❌ Ошибка публикации: ${data.message}`);
            }
        }
    } catch (error) {
        showMessage('danger', `❌ Ошибка: ${error.message}`);
    } finally {
        hideLoader();
    }
}

// Подтверждение кода Telegram
document.getElementById('codeForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const code = document.getElementById('telegram_code').value;
    
    showLoader();
    
    try {
        const response = await fetch('/verify_telegram_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ code })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showMessage('success', '✅ Код подтвержден! Теперь можно публиковать.');
            // Закрываем модальное окно
            bootstrap.Modal.getInstance(document.getElementById('telegramCodeModal')).hide();
            // Пробуем снова опубликовать
            publishPost();
        } else {
            showMessage('danger', `❌ Ошибка верификации: ${data.message}`);
        }
    } catch (error) {
        showMessage('danger', `❌ Ошибка: ${error.message}`);
    } finally {
        hideLoader();
    }
});

// Вспомогательные функции
function getTypeName(type) {
    const names = {
        'text': 'Текст',
        'image': 'Изображение',
        'headline': 'Заголовок'
    };
    return names[type] || type;
}

function showLoader() {
    document.getElementById('loader').classList.remove('d-none');
}

function hideLoader() {
    document.getElementById('loader').classList.add('d-none');
}

function showMessage(type, message) {
    const messagesDiv = document.getElementById('messages');
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    messagesDiv.appendChild(alertDiv);
    
    // Убираем автоматическое удаление - сообщения будут исчезать только при клике на крестик
}