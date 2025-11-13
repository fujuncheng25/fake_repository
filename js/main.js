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
});

let recognitionStream = null;
let recognitionVideo = null;
let recognitionCanvas = null;
let recognitionStatusEl = null;
let recognitionResultsEl = null;
let recognitionFileInput = null;

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
                // 用户已登录
                updateUIAfterLogin(user);
                
                // 显示上传按钮
                document.getElementById('uploadCatBtn').style.display = 'inline-block';
                
                // 如果是管理员，显示管理按钮
                if (user.is_admin) {
                    document.getElementById('adminBtn').style.display = 'inline-block';
                }
            } else {
                // 用户未登录
                updateUIAfterLogout();
            }
        })
        .catch(error => {
            console.error('Error checking auth status:', error);
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
            const catList = document.querySelector('.cat-list');
            if (!catList) return;
            
            catList.innerHTML = '';
            
            cats.forEach(cat => {
                const catCard = createCatCard(cat);
                catList.appendChild(catCard);
            });
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
    
    hardcodedCats.forEach(cat => {
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
    
    card.innerHTML = `
        ${imageHtml}
        <div class="info">
            <h3>${cat.name}</h3>
            <p><strong>年龄:</strong> ${cat.age}</p>
            <p><strong>性别:</strong> ${cat.gender}</p>
            <p>${cat.description || '暂无描述'}</p>
            <p><strong>绝育情况:</strong> ${cat.sterilized ? '已绝育' : '未绝育/未知'}</p>
            <p><strong>显著特征:</strong> ${cat.unique_markings || '暂无'}</p>
            <p><strong>特别说明:</strong> ${cat.special_notes || '暂无'}</p>
            <p><strong>最近位置:</strong> ${cat.last_known_location || '暂无记录'}</p>
            <button class="adopt-btn" data-cat-id="${cat.id}">我要领养</button>
        </div>
    `;
    
    // 绑定领养按钮事件
    const adoptBtn = card.querySelector('.adopt-btn');
    adoptBtn.addEventListener('click', function() {
        handleAdoptClick(cat.id);
    });
    
    return card;
}

// 处理领养点击事件
function handleAdoptClick(catId) {
    // Check if user is logged in
    fetch('/api/current_user')
        .then(response => response.json())
        .then(user => {
            if (!user.id) {
                alert('请先登录后再申请领养！');
                // Show login modal
                if (window.authSystem) {
                    window.authSystem.openModal('login');
                }
                return;
            }
            
            alert(`感谢您的爱心！您已申请领养猫咪（ID: ${catId}）。我们的工作人员会尽快与您联系。`);
        })
        .catch(error => {
            console.error('Error:', error);
            alert('请先登录后再申请领养！');
        });
}

// 模拟加载更多功能
function loadMoreCats() {
    console.log('加载更多猫咪信息...');
    // 在实际应用中，这里会从服务器获取更多数据
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

function recognizeCatImage(imageBlob, source) {
    const formData = new FormData();
    const filename = source === 'camera' ? `capture-${Date.now()}.jpg` : (imageBlob.name || `upload-${Date.now()}.jpg`);
    formData.append('image', imageBlob, filename);

    setRecognitionStatus('正在识别，请稍候…', 'info');

    fetch('/api/cats/recognize', {
        method: 'POST',
        body: formData,
        credentials: 'include'
    })
    .then(response => {
        if (response.status === 401) {
            setRecognitionStatus('请先登录后再使用猫脸识别功能。', 'error');
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
        setRecognitionStatus('识别完成。', 'success');
        renderRecognitionResults(data);
        if (source === 'upload' && recognitionFileInput) {
            recognitionFileInput.value = '';
        }
    })
    .catch(error => {
        if (error.message !== '未登录') {
            console.error('Recognition error:', error);
            setRecognitionStatus(error.message || '识别失败，请稍后重试。', 'error');
        }
    });
}

function renderRecognitionResults(result) {
    if (!recognitionResultsEl) return;
    recognitionResultsEl.innerHTML = '';

    const matches = result.matches || [];
    if (!matches.length) {
        recognitionResultsEl.innerHTML = '<p class="recognition-placeholder">未找到匹配的猫咪信息。您可以将照片提交给管理员补充到数据库中。</p>';
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

        recognitionResultsEl.appendChild(card);
    });
}

function setRecognitionStatus(message, type = 'info') {
    if (!recognitionStatusEl) return;
    recognitionStatusEl.textContent = message || '';
    recognitionStatusEl.className = `recognition-status ${type}`;
}