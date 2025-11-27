// 主应用程序逻辑
document.addEventListener('DOMContentLoaded', function() {
    // 初始化应用
    initializeApp();
    
    // 检查用户认证状态
    checkAuthStatus();
    
    // 加载猫咪信息
    loadCatData();
    
    // Fetch dynamic content
    fetchContent('home_intro', 'home-intro-title', 'home-intro-content');
    fetchContent('about_mission', 'about-mission-title', 'about-mission-content');

    setupRecognition();
    setupCatSearch();
    setupAdoptionModal();
    setupMobileCommandCenter();
    setupMobileCruiseFAB();
});

let recognitionStream = null;
let recognitionVideo = null;
let recognitionCanvas = null;
let recognitionStatusEl = null;
let recognitionResultsEl = null;
let recognitionFileInput = null;
let mobileCommandVideo = null;
let mobileCommandCanvas = null;
let mobileCommandStream = null;
let mobileCommandPanel = null;
let mobileStatusEl = null;
let mobileReportEl = null;
let mobileLogEl = null;
let mobileAutoActive = false;
let mobileAutoTimer = null;
let mobilePanelRetreated = false;
const MOBILE_PANEL_STORAGE_KEY = 'mobilePanelRetreated';
const DESKTOP_MODE_CLASS = 'desktop-ui-forced';
let mobilePanelGestureCleanup = null;
let allCats = [];
let filteredCats = [];
let currentUser = null;
let pendingAdoptionCat = null;

function fetchContent(contentId, titleElementId, contentElementId) {
    fetch(`/api/content/${contentId}`)
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            return null;
        })
        .then(data => {
            if (data) {
                const titleElement = document.getElementById(titleElementId);
                const contentElement = document.getElementById(contentElementId);
                if (titleElement) titleElement.textContent = data.title;
                if (contentElement) contentElement.textContent = data.content;
            }
        })
        .catch(error => {
            console.error('Error fetching content:', error);
        });
}

function initializeApp() {
    console.log('流浪猫公益项目应用已启动');
    
    // 绑定页面滚动事件
    window.addEventListener('scroll', handleScroll);
    
    // 绑定导航链接点击事件
    bindNavigationEvents();
    
    // 绑定认证相关按钮事件
    bindAuthEvents();
}

function handleScroll() {
    // 可以在这里添加滚动相关的功能
}

function bindNavigationEvents() {
    const navLinks = document.querySelectorAll('nav a');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            scrollToSection(targetId);
        });
    });
}

function bindAuthEvents() {
    // 绑定新按钮事件
    document.getElementById('uploadCatBtn').addEventListener('click', function() {
        window.location.href = '/upload';
    });
    
    document.addEventListener('click', function(e) {
        if (e.target && e.target.id === 'messagesBtn') {
            window.location.href = '/messages';
        }
    });
    
    document.getElementById('adminBtn').addEventListener('click', function() {
        window.location.href = '/admin';
    });
    
    // 绑定原来的登录/注册按钮事件
    if (window.authSystem) {
        document.getElementById('loginBtn').addEventListener('click', () => window.authSystem.openModal('login'));
        document.getElementById('registerBtn').addEventListener('click', () => window.authSystem.openModal('register'));
    }
}

function scrollToSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.scrollIntoView({ behavior: 'smooth' });
    }
}

// 检查用户认证状态
function checkAuthStatus() {
    fetch('/api/current_user')
        .then(response => response.json())
        .then(user => {
            if (user.id) {
                currentUser = user;
                // 用户已登录
                updateUIAfterLogin(user);
                
                // 显示上传按钮
                document.getElementById('uploadCatBtn').style.display = 'inline-block';
                
                // 如果是管理员，显示管理按钮
                if (user.is_admin) {
                    document.getElementById('adminBtn').style.display = 'inline-block';
                }
            } else {
                currentUser = null;
                // 用户未登录
                updateUIAfterLogout();
            }
        })
        .catch(error => {
            console.error('Error checking auth status:', error);
            currentUser = null;
            updateUIAfterLogout();
        });
}

// 登录后更新UI
function updateUIAfterLogin(user) {
    console.log('updateUIAfterLogin called with user:', user);
    const authButtons = document.querySelector('.auth-buttons');
    console.log('authButtons:', authButtons);
    if (authButtons) {
        // Hide login/register buttons
        const loginBtn = document.getElementById('loginBtn');
        const registerBtn = document.getElementById('registerBtn');
        if (loginBtn) {
            loginBtn.style.display = 'none';
            console.log('Hid login button');
        }
        if (registerBtn) {
            registerBtn.style.display = 'none';
            console.log('Hid register button');
        }
        
        // Show upload button
        const uploadBtn = document.getElementById('uploadCatBtn');
        if (uploadBtn) {
            uploadBtn.style.display = 'inline-block';
            console.log('Showed upload button');
        } else {
            console.log('Upload button not found');
        }
        
        // If admin, show admin button
        if (user.is_admin) {
            const adminBtn = document.getElementById('adminBtn');
            if (adminBtn) {
                adminBtn.style.display = 'inline-block';
                console.log('Showed admin button');
            } else {
                console.log('Admin button not found');
            }
        }
        
        // Add user welcome message and logout button if not already present
        let userInfo = document.querySelector('.user-info');
        if (!userInfo) {
            userInfo = document.createElement('div');
            userInfo.className = 'user-info';
            userInfo.innerHTML = `
                <span>欢迎，${user.name}</span>
                <button id="logoutBtn">退出</button>
            `;
            authButtons.appendChild(userInfo);
            
            // Bind logout event
            document.getElementById('logoutBtn').addEventListener('click', function() {
                logout();
            });
            console.log('Added user info and logout button');
        }
    } else {
        console.log('authButtons not found');
    }
}

// 登出后更新UI
function updateUIAfterLogout() {
    currentUser = null;
    const authButtons = document.querySelector('.auth-buttons');
    if (authButtons) {
        // Hide upload and admin buttons
        const uploadBtn = document.getElementById('uploadCatBtn');
        const adminBtn = document.getElementById('adminBtn');
        const messagesBtn = document.getElementById('messagesBtn');
        if (uploadBtn) uploadBtn.style.display = 'none';
        if (adminBtn) adminBtn.style.display = 'none';
        if (messagesBtn) messagesBtn.remove();
        
        // Show login/register buttons
        const loginBtn = document.getElementById('loginBtn');
        const registerBtn = document.getElementById('registerBtn');
        if (loginBtn) loginBtn.style.display = 'inline-block';
        if (registerBtn) registerBtn.style.display = 'inline-block';
        
        // Remove user info if present
        const userInfo = document.querySelector('.user-info');
        if (userInfo) userInfo.remove();
        
        // Re-bind events
        bindAuthEvents();
    }
}

// 登出功能
function logout() {
    fetch('/api/logout', {
        method: 'POST'
    })
    .then(() => {
        updateUIAfterLogout();
        // 重新加载页面以刷新状态
        window.location.reload();
    })
    .catch(error => console.error('Error:', error));
}

// 模拟猫咪数据
const catData = [
    {
        id: 1,
        name: "小花",
        age: "2岁",
        gender: "雌性",
        description: "性格温顺，喜欢与人亲近",
        image: "assets/cat1.jpg",
        sterilized: true,
        unique_markings: "额头有心形花纹",
        special_notes: "",
        last_known_location: ""
    },
    {
        id: 2,
        name: "小黑",
        age: "1.5岁",
        gender: "雄性",
        description: "活泼好动，好奇心强",
        image: "assets/cat2.jpg",
        sterilized: false,
        unique_markings: "",
        special_notes: "",
        last_known_location: ""
    },
    {
        id: 3,
        name: "小白",
        age: "3岁",
        gender: "雌性",
        description: "优雅安静，适合家庭饲养",
        image: "assets/cat3.jpg",
        sterilized: true,
        unique_markings: "",
        special_notes: "",
        last_known_location: ""
    },
    {
        id: 4,
        name: "小橘",
        age: "1岁",
        gender: "雄性",
        description: "贪吃可爱，非常亲人",
        image: "assets/cat4.jpg",
        sterilized: false,
        unique_markings: "",
        special_notes: "",
        last_known_location: ""
    }
];

// 加载猫咪信息
function loadCatData() {
    fetch('/api/cats')
        .then(response => response.json())
        .then(cats => {
            allCats = Array.isArray(cats) ? cats : [];
            filteredCats = [...allCats];
            renderCatCards(filteredCats);
        })
        .catch(error => {
            console.error('Error loading cats:', error);
            // Fallback to hardcoded data if API fails
            fallbackToHardcodedData();
        });
}

// Fallback to hardcoded data if API fails
function fallbackToHardcodedData() {
    const catList = document.querySelector('.cat-list');
    if (!catList) return;
    
    catList.innerHTML = '';
    
    const hardcodedCats = [
        {
            id: 1,
            name: "小花",
            age: "2岁",
            gender: "雌性",
            description: "性格温顺，喜欢与人亲近",
            image: "assets/cat1.jpg",
            sterilized: true,
            unique_markings: "额头有心形花纹",
            special_notes: "",
            last_known_location: ""
        },
        {
            id: 2,
            name: "小黑",
            age: "1.5岁",
            gender: "雄性",
            description: "活泼好动，好奇心强",
            image: "assets/cat2.jpg",
            sterilized: false,
            unique_markings: "",
            special_notes: "",
            last_known_location: ""
        },
        {
            id: 3,
            name: "小白",
            age: "3岁",
            gender: "雌性",
            description: "优雅安静，适合家庭饲养",
            image: "assets/cat3.jpg",
            sterilized: true,
            unique_markings: "",
            special_notes: "",
            last_known_location: ""
        },
        {
            id: 4,
            name: "小橘",
            age: "1岁",
            gender: "雄性",
            description: "贪吃可爱，非常亲人",
            image: "assets/cat4.jpg",
            sterilized: false,
            unique_markings: "",
            special_notes: "",
            last_known_location: ""
        }
    ];
    
    allCats = hardcodedCats;
    filteredCats = [...allCats];
    renderCatCards(filteredCats);
}

function renderCatCards(cats) {
    const catList = document.querySelector('.cat-list');
    if (!catList) return;
    catList.innerHTML = '';
    if (!cats || cats.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'no-cats';
        empty.textContent = '暂未找到符合条件的猫咪，请尝试其它关键词。';
        catList.appendChild(empty);
        return;
    }
    cats.forEach(cat => {
        const catCard = createCatCard(cat);
        catList.appendChild(catCard);
    });
}

// 创建猫咪卡片
function createCatCard(cat) {
    const card = document.createElement('div');
    card.className = 'cat-card';
    
    // Check if cat has an image path
    let imageHtml = '';
    if (cat.image_path) {
        imageHtml = `<img src="/${cat.image_path}" alt="${cat.name}" onerror="this.parentElement.innerHTML='<div class=\\'image-placeholder\\' style=\\'background-color: #f0f0f0; height: 200px; display: flex; align-items: center; justify-content: center;\\'><span>猫咪图片</span></div>';">`;
    } else {
        imageHtml = `<div class="image-placeholder" style="background-color: #f0f0f0; height: 200px; display: flex; align-items: center; justify-content: center;">
            <span>猫咪图片</span>
        </div>`;
    }
    
    const isAdopted = !!cat.is_adopted;
    const adoptButtonLabel = isAdopted ? '已被领养' : '我要领养';
    card.innerHTML = `
        ${imageHtml}
        <div class="info">
            <h3>${cat.name}</h3>
            ${isAdopted ? '<span class="cat-status cat-status-adopted">已被领养</span>' : ''}
            <p><strong>年龄:</strong> ${cat.age}</p>
            <p><strong>性别:</strong> ${cat.gender}</p>
            <p>${cat.description || '暂无描述'}</p>
            <p><strong>绝育情况:</strong> ${cat.sterilized ? '已绝育' : '未绝育/未知'}</p>
            <p><strong>显著特征:</strong> ${cat.unique_markings || '暂无'}</p>
            <p><strong>特别说明:</strong> ${cat.special_notes || '暂无'}</p>
            <p><strong>最近位置:</strong> ${cat.last_known_location || '暂无记录'}</p>
            <button class="adopt-btn" data-cat-id="${cat.id}" ${isAdopted ? 'disabled' : ''}>${adoptButtonLabel}</button>
        </div>
    `;
    
    // 绑定领养按钮事件
    const adoptBtn = card.querySelector('.adopt-btn');
    if (!isAdopted) {
        adoptBtn.addEventListener('click', function() {
            handleAdoptClick(cat.id);
        });
    }
    
    return card;
}

// 处理领养点击事件
function handleAdoptClick(catId) {
    if (!currentUser || !currentUser.id) {
        alert('请先登录后再申请领养！');
        if (window.authSystem) {
            window.authSystem.openModal('login');
        }
        return;
    }
    const targetCat = allCats.find(cat => parseInt(cat.id, 10) === parseInt(catId, 10));
    if (!targetCat) {
        alert('无法找到猫咪信息，请稍后再试。');
        return;
    }
    if (targetCat.is_adopted) {
        alert('这只猫咪已经被领养啦！');
        return;
    }
    openAdoptionModal(targetCat);
}

function setupCatSearch() {
    const searchInput = document.getElementById('catSearchInput');
    if (!searchInput) return;
    searchInput.addEventListener('input', (event) => {
        const query = event.target.value.trim();
        if (!query) {
            filteredCats = [...allCats];
        } else {
            filteredCats = allCats.filter(cat => matchesQuery(cat, query));
        }
        renderCatCards(filteredCats);
    });
}

function normalizeSearchText(text) {
    return (text || '').toString().toLowerCase();
}

function matchesQuery(cat, query) {
    const haystack = normalizeSearchText([
        cat.name,
        cat.age,
        cat.gender,
        cat.description,
        cat.special_notes,
        cat.unique_markings,
        cat.last_known_location
    ].join(' '));
    const cleanedQuery = query.toLowerCase();
    const terms = cleanedQuery.split(/\s+/).filter(Boolean);
    if (terms.length === 0) return true;
    return terms.every(term => {
        return haystack.includes(term) || isFuzzyMatch(haystack, term);
    });
}

function isFuzzyMatch(text, query) {
    let textIndex = 0;
    for (const char of query) {
        textIndex = text.indexOf(char, textIndex);
        if (textIndex === -1) {
            return false;
        }
        textIndex++;
    }
    return true;
}

function setupAdoptionModal() {
    const modal = document.getElementById('adoptionModal');
    if (!modal) return;
    const closeBtn = document.getElementById('closeAdoptionModal');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeAdoptionModal);
    }
    const form = document.getElementById('adoptionForm');
    if (form) {
        form.addEventListener('submit', submitAdoptionForm);
    }
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeAdoptionModal();
        }
    });
}

function openAdoptionModal(cat) {
    pendingAdoptionCat = cat;
    const modal = document.getElementById('adoptionModal');
    if (!modal) return;
    document.getElementById('adoptionCatName').textContent = `${cat.name} (ID: ${cat.id})`;
    document.getElementById('adoptionCatId').value = cat.id;
    document.getElementById('adoptionContact').value = currentUser && currentUser.email ? currentUser.email : '';
    document.getElementById('adoptionMessage').value = '';
    setAdoptionStatus('');
    modal.style.display = 'block';
}

function closeAdoptionModal() {
    const modal = document.getElementById('adoptionModal');
    if (modal) {
        modal.style.display = 'none';
    }
    pendingAdoptionCat = null;
}

function setAdoptionStatus(message, type = 'info') {
    const statusEl = document.getElementById('adoptionStatus');
    if (!statusEl) return;
    if (!message) {
        statusEl.style.display = 'none';
        return;
    }
    statusEl.textContent = message;
    statusEl.style.display = 'block';
    statusEl.className = `status-message status-${type}`;
}

function submitAdoptionForm(event) {
    event.preventDefault();
    if (!pendingAdoptionCat) {
        setAdoptionStatus('未找到猫咪信息，请关闭后重试。', 'error');
        return;
    }
    const contact = document.getElementById('adoptionContact').value.trim();
    const message = document.getElementById('adoptionMessage').value.trim();
    if (!contact) {
        setAdoptionStatus('请填写联系方式。', 'error');
        return;
    }
    setAdoptionStatus('正在提交申请…', 'info');
    fetch(`/api/cats/${pendingAdoptionCat.id}/adopt`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            contact_info: contact,
            message: message
        })
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ ok, data }) => {
        if (ok) {
            setAdoptionStatus('申请已提交，感谢您的爱心！', 'success');
            setTimeout(() => {
                closeAdoptionModal();
            }, 1500);
        } else {
            throw new Error(data.error || '提交失败，请稍后再试。');
        }
    })
    .catch(error => {
        console.error('Adoption error:', error);
        setAdoptionStatus(error.message || '提交失败，请稍后再试。', 'error');
    });
}

// 模拟加载更多功能
function loadMoreCats() {
    console.log('加载更多猫咪信息...');
    // 在实际应用中，这里会从服务器获取更多数据
}

// ---------------- 移动指挥面板（移动端专属） ----------------

function setupMobileCommandCenter() {
    if (!shouldActivateMobileUI()) {
        return;
    }
    if (document.body.classList.contains(DESKTOP_MODE_CLASS)) {
        return;
    }
    if (mobilePanelRetreated) {
        return;
    }
    if (isMobilePanelRetreatedInStorage()) {
        mobilePanelRetreated = true;
        updateMobileCruiseFABVisibility();
        return;
    }
    if (document.getElementById('mobileCommandCenter')) {
        return;
    }

    document.body.classList.add('mobile-ui-active');
    injectMobileCommandMarkup();

    mobileCommandPanel = document.getElementById('mobileCommandPanel');
    mobileCommandVideo = document.getElementById('mobileCommandVideo');
    mobileCommandCanvas = document.getElementById('mobileCommandCanvas');
    mobileStatusEl = document.getElementById('mobileStatus');
    mobileReportEl = document.getElementById('mobileReport');
    mobileLogEl = document.getElementById('mobileLog');

    const autoBtn = document.getElementById('mobileAutoBtn');
    const snapBtn = document.getElementById('mobileSnapBtn');
    const retreatBtn = document.getElementById('mobileRetreatBtn');

    autoBtn.addEventListener('click', () => toggleMobileAuto(autoBtn));
    snapBtn.addEventListener('click', () => captureMobileSnapshot());
    retreatBtn.addEventListener('click', retreatMobilePanelToDesktop);
    setupMobilePanelGestures();

    window.addEventListener('beforeunload', stopMobileCamera);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopMobileCamera();
        }
    });
}

function shouldActivateMobileUI() {
    const userAgentMobile = /Mobile|Android|iP(ad|hone|od)/i.test(navigator.userAgent);
    const touchCapable = ('ontouchstart' in window) || navigator.maxTouchPoints > 1;
    const narrowViewport = window.matchMedia('(max-width: 768px)').matches;
    return userAgentMobile || (touchCapable && narrowViewport);
}

function retreatMobilePanelToDesktop() {
    if (mobilePanelRetreated) {
        return;
    }
    mobilePanelRetreated = true;
    persistMobilePanelRetreatFlag();
    activateDesktopView();
    if (mobileCommandPanel) {
        mobileCommandPanel.classList.remove('is-dragging');
        mobileCommandPanel.style.transition = 'transform 0.25s ease';
        mobileCommandPanel.style.transform = 'translateY(120%)';
        mobileCommandPanel.addEventListener('transitionend', teardownMobileCommandCenter, { once: true });
        setTimeout(teardownMobileCommandCenter, 300);
    } else {
        teardownMobileCommandCenter();
    }
}

function teardownMobileCommandCenter() {
    if (mobilePanelGestureCleanup) {
        mobilePanelGestureCleanup();
        mobilePanelGestureCleanup = null;
    }
    stopMobileCamera();
    document.body.classList.remove('mobile-ui-active');
    const center = document.getElementById('mobileCommandCenter');
    if (center && center.parentNode) {
        center.parentNode.removeChild(center);
    }
    mobileCommandPanel = null;
    mobileCommandVideo = null;
    mobileCommandCanvas = null;
    mobileStatusEl = null;
    mobileReportEl = null;
    mobileLogEl = null;
    mobileAutoActive = false;
    clearInterval(mobileAutoTimer);
    mobileAutoTimer = null;
    if (mobileCommandPanel) {
        mobileCommandPanel.style.transform = '';
        mobileCommandPanel.style.transition = '';
    }
    mobileCommandPanel = null;
}

function setupMobilePanelGestures() {
    if (!mobileCommandPanel) {
        return;
    }
    if (mobilePanelGestureCleanup) {
        mobilePanelGestureCleanup();
    }

    const panel = mobileCommandPanel;
    let startY = 0;
    let currentOffset = 0;
    let dragging = false;

    const resetTransform = () => {
        panel.classList.remove('is-dragging');
        panel.style.transition = '';
        panel.style.transform = '';
        currentOffset = 0;
        dragging = false;
    };

    const handleStart = event => {
        if (event.touches && event.touches.length > 1) {
            return;
        }
        startY = (event.touches ? event.touches[0] : event).clientY;
        currentOffset = 0;
        dragging = false;
        panel.classList.remove('is-dragging');
        panel.style.transition = '';
    };

    const handleMove = event => {
        if (event.touches && event.touches.length > 1) {
            return;
        }
        const y = (event.touches ? event.touches[0] : event).clientY;
        const delta = y - startY;
        const pullingDown = delta > 0;
        if (!pullingDown || panel.scrollTop > 0) {
            if (dragging) {
                resetTransform();
            }
            return;
        }
        if (!dragging && Math.abs(delta) < 8) {
            return;
        }
        if (!dragging) {
            dragging = true;
            panel.classList.add('is-dragging');
        }
        currentOffset = Math.min(delta, 200);
        panel.style.transform = `translateY(${currentOffset}px)`;
        if (event.cancelable) {
            event.preventDefault();
        }
    };

    const commitPosition = () => {
        panel.classList.remove('is-dragging');
        if (currentOffset > 120) {
            retreatMobilePanelToDesktop();
        } else if (currentOffset > 0) {
            panel.style.transition = 'transform 0.2s ease';
            panel.style.transform = 'translateY(0)';
            panel.addEventListener('transitionend', () => {
                panel.style.transition = '';
                panel.style.transform = '';
            }, { once: true });
        } else {
            panel.style.transform = '';
        }
        dragging = false;
        currentOffset = 0;
    };

    const handleEnd = () => {
        if (!dragging) {
            return;
        }
        commitPosition();
    };

    panel.addEventListener('touchstart', handleStart, { passive: true });
    panel.addEventListener('touchmove', handleMove, { passive: false });
    panel.addEventListener('touchend', handleEnd);
    panel.addEventListener('touchcancel', handleEnd);

    mobilePanelGestureCleanup = () => {
        panel.removeEventListener('touchstart', handleStart);
        panel.removeEventListener('touchmove', handleMove);
        panel.removeEventListener('touchend', handleEnd);
        panel.removeEventListener('touchcancel', handleEnd);
        resetTransform();
    };
}

function activateDesktopView() {
    document.body.classList.add(DESKTOP_MODE_CLASS);
    document.body.classList.remove('mobile-ui-active');
    const center = document.getElementById('mobileCommandCenter');
    if (center) {
        center.style.opacity = '0';
        center.style.pointerEvents = 'none';
    }
    requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    updateMobileCruiseFABVisibility();
    setTimeout(() => {
        if (document.body.classList.contains(DESKTOP_MODE_CLASS)) {
            window.location.reload();
        }
    }, 400);
}

function getSafeSessionStorage() {
    try {
        return window.sessionStorage;
    } catch (error) {
        console.debug('Session storage unavailable:', error);
        return null;
    }
}

function isMobilePanelRetreatedInStorage() {
    const storage = getSafeSessionStorage();
    if (!storage) {
        return false;
    }
    try {
        return storage.getItem(MOBILE_PANEL_STORAGE_KEY) === 'true';
    } catch (error) {
        console.debug('Session storage read failed:', error);
        return false;
    }
}

function persistMobilePanelRetreatFlag() {
    const storage = getSafeSessionStorage();
    if (!storage) {
        return;
    }
    try {
        storage.setItem(MOBILE_PANEL_STORAGE_KEY, 'true');
    } catch (error) {
        console.debug('Session storage write failed:', error);
    }
}

function injectMobileCommandMarkup() {
    if (document.getElementById('mobileCommandCenter')) {
        return;
    }
    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
        <div class="mobile-command-center" id="mobileCommandCenter" aria-live="polite">
            <div class="mobile-panel" id="mobileCommandPanel">
                <div class="mobile-panel-header">
                    <div>
                        <span class="mobile-chip">CATalist</span>
                        <h3>巡航识别面板</h3>
                    </div>
                    <button id="mobileRetreatBtn" class="mobile-retreat-btn" aria-label="退出巡航面板">⇤</button>
                </div>
                <div class="mobile-body">
                    <div class="mobile-viewfinder">
                        <video id="mobileCommandVideo" autoplay muted playsinline></video>
                        <canvas id="mobileCommandCanvas" width="640" height="480" style="display:none;"></canvas>
                        <div class="mobile-scan-veil"></div>
                    </div>
                    <div class="mobile-controls">
                        <button id="mobileAutoBtn" class="primary">开始巡航</button>
                        <button id="mobileSnapBtn" class="secondary">即时识别</button>
                    </div>
                    <div class="mobile-status" id="mobileStatus">待命中…</div>
                    <div class="mobile-report" id="mobileReport">尚未识别到猫咪。</div>
                    <div class="mobile-log" id="mobileLog">
                        <p>系统已部署，等待启动。</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(wrapper.firstElementChild);
}

function toggleMobileAuto(autoBtn) {
    if (!mobileAutoActive) {
        startMobileCamera()
            .then(() => {
                mobileAutoActive = true;
                autoBtn.textContent = '暂停巡航';
                updateMobileStatus('自动巡航已开启。', 'success');
                appendMobileLog('启动连续巡航识别。');
                startMobileAutoLoop();
            })
            .catch(() => {});
    } else {
        mobileAutoActive = false;
        autoBtn.textContent = '开始巡航';
        clearInterval(mobileAutoTimer);
        mobileAutoTimer = null;
        updateMobileStatus('巡航已暂停，可随时手动识别。', 'info');
        appendMobileLog('巡航暂停，等待下一次指令。');
    }
}

function captureMobileSnapshot() {
    startMobileCamera()
        .then(() => {
            mobileAutoActive = false;
            const autoBtn = document.getElementById('mobileAutoBtn');
            if (autoBtn) {
                autoBtn.textContent = '开始巡航';
            }
            clearInterval(mobileAutoTimer);
            mobileAutoTimer = null;
            captureMobileFrame(true);
        })
        .catch(() => {});
}

function startMobileCamera() {
    if (mobileCommandStream) {
        return Promise.resolve();
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        updateMobileStatus('当前浏览器不支持摄像头访问。', 'error');
        appendMobileLog('无法开启摄像头，请尝试使用桌面模式。');
        return Promise.reject(new Error('unsupported'));
    }
    updateMobileStatus('正在唤醒摄像头…', 'info');
    return navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
        .then(stream => {
            mobileCommandStream = stream;
            if (mobileCommandVideo) {
                mobileCommandVideo.srcObject = stream;
                mobileCommandVideo.play();
            }
            appendMobileLog('摄像头已上线。');
            return stream;
        })
        .catch(error => {
            console.error('Mobile camera error:', error);
            updateMobileStatus('无法开启摄像头，请检查权限。', 'error');
            appendMobileLog('摄像头访问被拒绝。');
            throw error;
        });
}

function startMobileAutoLoop() {
    clearInterval(mobileAutoTimer);
    mobileAutoTimer = setInterval(() => {
        if (mobileAutoActive) {
            captureMobileFrame(false);
        }
    }, 4500);
    captureMobileFrame(false);
}

function stopMobileCamera() {
    if (mobileCommandStream) {
        mobileCommandStream.getTracks().forEach(track => track.stop());
        mobileCommandStream = null;
    }
    if (mobileCommandVideo) {
        mobileCommandVideo.srcObject = null;
    }
    clearInterval(mobileAutoTimer);
    mobileAutoTimer = null;
    mobileAutoActive = false;
}

function captureMobileFrame(manual = false) {
    if (!mobileCommandStream || !mobileCommandVideo || !mobileCommandCanvas) {
        updateMobileStatus('摄像头未就绪。', 'error');
        return;
    }
    if (!mobileCommandVideo.videoWidth || !mobileCommandVideo.videoHeight) {
        updateMobileStatus('正在对焦，请稍后。', 'info');
        return;
    }

    mobileCommandCanvas.width = mobileCommandVideo.videoWidth;
    mobileCommandCanvas.height = mobileCommandVideo.videoHeight;
    const ctx = mobileCommandCanvas.getContext('2d');
    if (!ctx) {
        updateMobileStatus('画面不可用。', 'error');
        return;
    }
    ctx.drawImage(mobileCommandVideo, 0, 0, mobileCommandCanvas.width, mobileCommandCanvas.height);

    mobileCommandCanvas.toBlob(blob => {
        if (!blob) {
            updateMobileStatus('采样失败，请重试。', 'error');
            return;
        }
        recognizeCatImage(blob, manual ? 'mobile-manual' : 'mobile-auto', {
            onStatus: updateMobileStatus,
            onResults: handleMobileRecognitionResults
        });
        appendMobileLog(manual ? '执行一次手动识别。' : '巡航识别已提交。');
    }, 'image/jpeg', 0.9);
}

function updateMobileStatus(message, type = 'info') {
    if (!mobileStatusEl) return;
    mobileStatusEl.textContent = message || '';
    mobileStatusEl.classList.remove('status-info', 'status-success', 'status-error');
    mobileStatusEl.classList.add(`status-${type}`);
}

function updateMobileReport(message, type = 'info') {
    if (!mobileReportEl) return;
    mobileReportEl.textContent = message || '';
    mobileReportEl.classList.remove('status-info', 'status-success', 'status-error');
    mobileReportEl.classList.add(`status-${type}`);
}

function appendMobileLog(message) {
    if (!mobileLogEl) return;
    const entry = document.createElement('p');
    const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    entry.textContent = `[${timestamp}] ${message}`;
    mobileLogEl.prepend(entry);
    while (mobileLogEl.children.length > 5) {
        mobileLogEl.removeChild(mobileLogEl.lastChild);
    }
}

function handleMobileRecognitionResults(result) {
    if (!result) {
        updateMobileReport('识别失败，请稍后再试。', 'error');
        return;
    }
    const matches = Array.isArray(result.matches) ? result.matches : [];
    if (!matches.length) {
        updateMobileReport('未识别到已登记的猫咪。', 'info');
        appendMobileLog('暂无匹配结果。');
        return;
    }
    const topMatch = matches[0];
    reportMobileRecognition(topMatch);
}

function reportMobileRecognition(match) {
    const cat = match && match.cat ? match.cat : null;
    const name = cat && cat.name ? cat.name : '未知猫咪';
    const similarity = typeof match.similarity === 'number' ? `${Math.round(match.similarity * 100)}%` : '未知';
    const location = cat && cat.last_known_location ? cat.last_known_location : '位置待补充';
    const message = `识别报告 · ${name} · 匹配度 ${similarity} · 最近位置 ${location}`;
    updateMobileReport(message, 'success');
    appendMobileLog(`识别命中：${name}（${similarity}）。`);
    if (navigator.vibrate) {
        navigator.vibrate(120);
    }
}

// ---------------- 猫脸识别功能 ----------------

function setupRecognition() {
    recognitionVideo = document.getElementById('recognitionVideo');
    recognitionCanvas = document.getElementById('recognitionCanvas');
    recognitionStatusEl = document.getElementById('recognitionStatus');
    recognitionResultsEl = document.getElementById('recognitionResults');
    recognitionFileInput = document.getElementById('recognitionFileInput');

    const startCameraBtn = document.getElementById('startCameraBtn');
    const capturePhotoBtn = document.getElementById('capturePhotoBtn');
    const uploadRecognizeBtn = document.getElementById('uploadRecognizeBtn');

    if (!recognitionVideo || !recognitionCanvas || !startCameraBtn || !capturePhotoBtn || !uploadRecognizeBtn) {
        return;
    }

    startCameraBtn.addEventListener('click', startRecognitionCamera);
    capturePhotoBtn.addEventListener('click', captureRecognitionPhoto);
    uploadRecognizeBtn.addEventListener('click', handleRecognitionUpload);

    window.addEventListener('beforeunload', stopRecognitionCamera);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopRecognitionCamera();
        }
    });
}

function startRecognitionCamera() {
    if (recognitionStream) {
        setRecognitionStatus('摄像头已开启。', 'success');
        return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setRecognitionStatus('当前浏览器不支持摄像头访问，请尝试上传图片识别。', 'error');
        return;
    }

    setRecognitionStatus('正在请求摄像头权限…', 'info');

    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
        .then(stream => {
            recognitionStream = stream;
            recognitionVideo.srcObject = stream;
            recognitionVideo.play();
            setRecognitionStatus('摄像头已开启，可以点击“拍摄并识别”。', 'success');
        })
        .catch(error => {
            console.error('Error starting camera:', error);
            setRecognitionStatus('无法开启摄像头，请检查权限或直接上传图片。', 'error');
        });
}

function stopRecognitionCamera() {
    if (recognitionStream) {
        recognitionStream.getTracks().forEach(track => track.stop());
        recognitionStream = null;
    }
    if (recognitionVideo) {
        recognitionVideo.srcObject = null;
    }
}

function captureRecognitionPhoto() {
    if (!recognitionStream) {
        setRecognitionStatus('请先点击“开启摄像头”。', 'error');
        return;
    }
    if (!recognitionCanvas || !recognitionVideo) {
        setRecognitionStatus('系统初始化失败，请刷新页面重试。', 'error');
        return;
    }

    const context = recognitionCanvas.getContext('2d');
    recognitionCanvas.width = recognitionVideo.videoWidth || 640;
    recognitionCanvas.height = recognitionVideo.videoHeight || 480;
    context.drawImage(recognitionVideo, 0, 0, recognitionCanvas.width, recognitionCanvas.height);

    recognitionCanvas.toBlob(blob => {
        if (!blob) {
            setRecognitionStatus('拍照失败，请重试。', 'error');
            return;
        }
        recognizeCatImage(blob, 'camera');
    }, 'image/jpeg', 0.9);
}

function handleRecognitionUpload() {
    if (!recognitionFileInput || !recognitionFileInput.files.length) {
        setRecognitionStatus('请先选择要上传的图片。', 'error');
        return;
    }
    const file = recognitionFileInput.files[0];
    recognizeCatImage(file, 'upload');
}

function recognizeCatImage(imageBlob, source, options = {}) {
    const statusEl = options.statusEl || recognitionStatusEl;
    const statusHandler = typeof options.onStatus === 'function'
        ? options.onStatus
        : (message, type) => setRecognitionStatus(message, type, statusEl);
    const onResults = typeof options.onResults === 'function'
        ? options.onResults
        : (data) => renderRecognitionResults(data);

    const formData = new FormData();
    const filename = source === 'camera' ? `capture-${Date.now()}.jpg` : (imageBlob.name || `upload-${Date.now()}.jpg`);
    formData.append('image', imageBlob, filename);

    statusHandler('正在识别，请稍候…', 'info');

    return fetch('/api/cats/recognize', {
        method: 'POST',
        body: formData,
        credentials: 'include'
    })
    .then(response => {
        if (response.status === 401) {
            statusHandler('请先登录后再使用猫脸识别功能。', 'error');
            if (window.authSystem) {
                window.authSystem.openModal('login');
            }
            throw new Error('未登录');
        }
        return response.json().then(data => ({ ok: response.ok, data }));
    })
    .then(({ ok, data }) => {
        if (!ok) {
            throw new Error(data.error || '识别失败，请稍后重试。');
        }
        statusHandler('识别完成。', 'success');
        onResults(data);
        if (source === 'upload' && recognitionFileInput) {
            recognitionFileInput.value = '';
        }
    })
    .catch(error => {
        if (error.message !== '未登录') {
            console.error('Recognition error:', error);
            statusHandler(error.message || '识别失败，请稍后重试。', 'error');
        }
    });
}

function renderRecognitionResults(result, targetEl = recognitionResultsEl) {
    if (!targetEl) return;
    targetEl.innerHTML = '';

    const matches = result.matches || [];
    if (!matches.length) {
        targetEl.innerHTML = '<p class="recognition-placeholder">未找到匹配的猫咪信息。您可以将照片提交给管理员补充到数据库中。</p>';
        return;
    }

    matches.forEach(match => {
        const card = document.createElement('div');
        card.className = 'recognition-result-card';

        const similarity = typeof match.similarity === 'number' ? Math.round(match.similarity * 100) : null;
        const similarityText = similarity !== null ? `${similarity}%` : '未知';
        const matchBadge = match.matched ? '<span class="recognition-badge" style="background-color:#d4edda;color:#155724;">可能是已登记的猫咪</span>' : '<span class="recognition-badge">待确认</span>';
        const distanceText = typeof match.hamming_distance === 'number' ? `${match.hamming_distance}` : '—';

        if (match.cat) {
            const cat = match.cat;
            const sterilizedText = cat.sterilized ? '已绝育' : '未绝育/未知';
            const microchipText = cat.microchipped ? '有芯片' : '无芯片/未知';
            const locationText = cat.last_known_location || '暂无记录';
            const notes = cat.special_notes || '暂无说明';
            const markings = cat.unique_markings || '暂无描述';
            const referenceImage = match.reference_image_path ? `<img src="/${match.reference_image_path}" alt="${cat.name || '参考图'}" style="width:100%;max-width:240px;border-radius:6px;margin-top:8px;">` : '';

            card.innerHTML = `
                <h3>${cat.name || '未命名猫咪'}</h3>
                <p>${matchBadge}<span class="recognition-badge">匹配度 ${similarityText}</span><span class="recognition-badge">哈希距离 ${distanceText}</span></p>
                <p><strong>编号:</strong> ${cat.identification_code || '暂无'}</p>
                <p><strong>年龄:</strong> ${cat.age || '未知'} · <strong>性别:</strong> ${cat.gender || '未知'}</p>
                <p><strong>绝育情况:</strong> ${sterilizedText} · <strong>芯片:</strong> ${microchipText}</p>
                <p><strong>显著特征:</strong> ${markings}</p>
                <p><strong>最新位置:</strong> ${locationText}</p>
                <p><strong>档案备注:</strong> ${notes}</p>
                ${referenceImage}
            `;
        } else {
            card.innerHTML = `
                <h3>未找到匹配的档案</h3>
                <p>${matchBadge}<span class="recognition-badge">匹配度 ${similarityText}</span><span class="recognition-badge">哈希距离 ${distanceText}</span></p>
                <p>当前数据库中暂无与该照片高度相似的猫咪，您可以联系管理员补充档案。</p>
            `;
        }

        targetEl.appendChild(card);
    });
}

function setRecognitionStatus(message, type = 'info', targetEl = recognitionStatusEl) {
    if (!targetEl) return;
    targetEl.textContent = message || '';
    targetEl.className = `recognition-status ${type}`;
}

function setupMobileCruiseFAB() {
    if (!shouldActivateMobileUI()) {
        return;
    }
    let fab = document.getElementById('mobileCruiseFAB');
    if (!fab) {
        fab = document.createElement('button');
        fab.id = 'mobileCruiseFAB';
        fab.className = 'mobile-cruise-fab';
        fab.setAttribute('aria-label', '打开巡航识别面板');
        fab.innerHTML = '🚢';
        fab.addEventListener('click', reactivateMobileCruisePanel);
        document.body.appendChild(fab);
    }
    updateMobileCruiseFABVisibility();
}

function updateMobileCruiseFABVisibility() {
    const fab = document.getElementById('mobileCruiseFAB');
    if (!fab) {
        return;
    }
    if (!shouldActivateMobileUI()) {
        fab.style.display = 'none';
        return;
    }
    const shouldShow = document.body.classList.contains(DESKTOP_MODE_CLASS) || 
                       isMobilePanelRetreatedInStorage() || 
                       mobilePanelRetreated;
    if (shouldShow) {
        fab.style.display = 'flex';
    } else {
        fab.style.display = 'none';
    }
}

function reactivateMobileCruisePanel() {
    mobilePanelRetreated = false;
    const storage = getSafeSessionStorage();
    if (storage) {
        try {
            storage.removeItem(MOBILE_PANEL_STORAGE_KEY);
        } catch (error) {
            console.debug('Session storage remove failed:', error);
        }
    }
    document.body.classList.remove(DESKTOP_MODE_CLASS);
    const center = document.getElementById('mobileCommandCenter');
    if (center && center.parentNode) {
        center.parentNode.removeChild(center);
    }
    updateMobileCruiseFABVisibility();
    setupMobileCommandCenter();
}