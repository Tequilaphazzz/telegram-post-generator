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

// Глобальная переменная для хранения данных публикации
let pendingPublishData = null;

// Публикация поста с правильной обработкой авторизации
async function publishPost(isRetry = false) {
    // Если это не повторная попытка, проверяем одобрения
    if (!isRetry) {
        if (!approvals.text || !approvals.image || !approvals.headline) {
            showMessage('warning', '⚠️ Пожалуйста, одобрите все элементы перед публикацией');
            return;
        }

        // Сохраняем данные для возможной повторной публикации
        const skipStories = document.getElementById('skipStories').checked;
        const storyType = document.querySelector('input[name="storyType"]:checked').value;

        pendingPublishData = {
            story_type: skipStories ? 'none' : storyType
        };
    }

    // Формируем сообщение о публикации
    let publishingMsg = '📤 Публикация в Telegram';
    if (pendingPublishData.story_type !== 'none') {
        if (pendingPublishData.story_type === 'channel') {
            publishingMsg += ' (пост + Story в канал)';
        } else if (pendingPublishData.story_type === 'personal') {
            publishingMsg += ' (пост + личная Story)';
        } else if (pendingPublishData.story_type === 'both') {
            publishingMsg += ' (пост + обе Stories)';
        }
    } else {
        publishingMsg += ' (только пост, без Stories)';
    }
    publishingMsg += '...';

    showLoader();
    showMessage('info', publishingMsg);

    try {
        const response = await fetch('/publish_post', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(pendingPublishData)
        });

        const data = await response.json();

        // Обрабатываем разные статусы
        if (data.status === 'success') {
            // Успешная публикация
            showMessage('success', '🎉 Публикация завершена успешно!');

            // Показываем детали
            if (data.details && data.details.length > 0) {
                let detailsMsg = '<strong>📋 Результаты:</strong><br>';
                data.details.forEach(detail => {
                    detailsMsg += `${detail}<br>`;
                });
                showMessage('info', detailsMsg);
            }

            // Показываем предупреждения
            if (data.warnings && data.warnings.length > 0) {
                let warningsMsg = '<strong>⚠️ Предупреждения:</strong><br>';
                data.warnings.forEach(warning => {
                    warningsMsg += `• ${warning}<br>`;
                });
                showMessage('warning', warningsMsg);
            }

            // Очищаем форму после успешной публикации
            clearAfterPublish();

        } else if (data.status === 'auth_required' || data.need_code) {
            // Требуется авторизация
            hideLoader();
            showMessage('info', '📱 Требуется код подтверждения из Telegram');

            // Автоматически показываем модальное окно для кода
            const modal = new bootstrap.Modal(document.getElementById('telegramCodeModal'));
            modal.show();

            // Обновляем обработчик формы для повторной публикации после верификации
            document.getElementById('codeForm').onsubmit = async function(e) {
                e.preventDefault();
                await verifyCodeAndRetryPublish();
            };

        } else if (data.status === 'partial') {
            // Частичный успех
            showMessage('warning', '⚠️ Публикация завершена с ошибками');

            if (data.warnings && data.warnings.length > 0) {
                let warningsMsg = '<strong>Ошибки:</strong><br>';
                data.warnings.forEach(warning => {
                    warningsMsg += `• ${warning}<br>`;
                });
                showMessage('danger', warningsMsg);
            }

            clearAfterPublish();

        } else if (data.status === 'timeout') {
            // Таймаут
            showMessage('warning', '⏱️ Превышено время ожидания');
            showMessage('info', 'Проверьте Telegram. Если пост не опубликован, попробуйте ещё раз.');

            // Предлагаем повторить
            if (confirm('Попробовать опубликовать ещё раз?')) {
                await publishPost(true);
            }

        } else if (data.status === 'unknown') {
            // Неизвестный статус
            showMessage('warning', '❓ Статус публикации неизвестен');
            showMessage('info', 'Проверьте Telegram. Возможно, пост был опубликован.');

        } else {
            // Ошибка
            showMessage('danger', `❌ Ошибка: ${data.message || 'Неизвестная ошибка'}`);

            // Если ошибка связана с авторизацией
            if (data.message && (
                data.message.includes('верификация') ||
                data.message.includes('авторизация') ||
                data.message.includes('код')
            )) {
                // Показываем модальное окно для кода
                const modal = new bootstrap.Modal(document.getElementById('telegramCodeModal'));
                modal.show();
            }
        }

    } catch (error) {
        showMessage('danger', `❌ Ошибка сети: ${error.message}`);

        // Предлагаем повторить
        if (confirm('Произошла ошибка сети. Попробовать ещё раз?')) {
            await publishPost(true);
        }

    } finally {
        hideLoader();
    }
}

// Верификация кода и повторная публикация
async function verifyCodeAndRetryPublish() {
    const code = document.getElementById('telegram_code').value.trim();

    if (!code) {
        showMessage('warning', '⚠️ Введите код подтверждения');
        return;
    }

    showLoader();
    showMessage('info', '🔐 Проверка кода...');

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
            showMessage('success', '✅ Код подтвержден!');

            // Закрываем модальное окно
            const modal = bootstrap.Modal.getInstance(document.getElementById('telegramCodeModal'));
            modal.hide();

            // Очищаем поле кода
            document.getElementById('telegram_code').value = '';

            // Если нужно повторить публикацию
            if (data.retry_publish && pendingPublishData) {
                showMessage('info', '🔄 Повторная попытка публикации...');
                setTimeout(() => {
                    publishPost(true);
                }, 1000);
            }

        } else {
            showMessage('danger', `❌ ${data.message || 'Неверный код'}`);

            if (data.need_2fa) {
                showMessage('warning', '🔐 Требуется пароль двухфакторной аутентификации');
                showMessage('info', 'Временно отключите 2FA в настройках Telegram и попробуйте снова');
            }
        }

    } catch (error) {
        showMessage('danger', `❌ Ошибка верификации: ${error.message}`);
    } finally {
        hideLoader();
    }
}

// Очистка после успешной публикации
function clearAfterPublish() {
    // Очищаем форму и предпросмотр
    document.getElementById('topic').value = '';
    document.getElementById('previewCard').style.display = 'none';
    resetApprovals();
    pendingPublishData = null;
}

// Обновляем обработчик формы с кодом (если он уже есть)
document.addEventListener('DOMContentLoaded', function() {
    const codeForm = document.getElementById('codeForm');
    if (codeForm) {
        codeForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            await verifyCodeAndRetryPublish();
        });
    }
});

// Добавляем обработчик для кнопки публикации
document.addEventListener('DOMContentLoaded', function() {
    const publishBtn = document.getElementById('publishBtn');
    if (publishBtn) {
        publishBtn.onclick = function() {
            publishPost(false);
        };
    }
});

// Добавляем функцию проверки поддержки Stories
async function checkStorySupport() {
    const telegram_group = document.getElementById('telegram_group').value;

    if (!telegram_group) {
        return;
    }

    try {
        const response = await fetch('/check_story_support', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ group_username: telegram_group })
        });

        const data = await response.json();

        if (data.status === 'success' && data.info) {
            // Обновляем UI в зависимости от поддержки Stories
            if (!data.info.supports_stories) {
                showMessage('info', 'ℹ️ Этот канал/группа может не поддерживать Stories. Будет использован альтернативный метод.');
            }
        }
    } catch (error) {
        console.error('Ошибка проверки поддержки Stories:', error);
    }
}

// Вызываем проверку при изменении группы
document.getElementById('telegram_group').addEventListener('blur', checkStorySupport);

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