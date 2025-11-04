// 主应用程序逻辑
document.addEventListener('DOMContentLoaded', function() {
    // 初始化应用
    initializeApp();
    
    // 加载猫咪信息
    loadCatData();
});

function initializeApp() {
    console.log('流浪猫公益项目应用已启动');
    
    // 绑定页面滚动事件
    window.addEventListener('scroll', handleScroll);
    
    // 绑定导航链接点击事件
    bindNavigationEvents();
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

function scrollToSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.scrollIntoView({ behavior: 'smooth' });
    }
}

// 模拟猫咪数据
const catData = [
    {
        id: 1,
        name: "小花",
        age: "2岁",
        gender: "雌性",
        description: "性格温顺，喜欢与人亲近",
        image: "assets/cat1.jpg"
    },
    {
        id: 2,
        name: "小黑",
        age: "1.5岁",
        gender: "雄性",
        description: "活泼好动，好奇心强",
        image: "assets/cat2.jpg"
    },
    {
        id: 3,
        name: "小白",
        age: "3岁",
        gender: "雌性",
        description: "优雅安静，适合家庭饲养",
        image: "assets/cat3.jpg"
    },
    {
        id: 4,
        name: "小橘",
        age: "1岁",
        gender: "雄性",
        description: "贪吃可爱，非常亲人",
        image: "assets/cat4.jpg"
    }
];

// 加载猫咪信息
function loadCatData() {
    const catList = document.querySelector('.cat-list');
    if (!catList) return;
    
    catList.innerHTML = '';
    
    catData.forEach(cat => {
        const catCard = createCatCard(cat);
        catList.appendChild(catCard);
    });
}

// 创建猫咪卡片
function createCatCard(cat) {
    const card = document.createElement('div');
    card.className = 'cat-card';
    card.innerHTML = `
        <div class="image-placeholder" style="background-color: #f0f0f0; height: 200px; display: flex; align-items: center; justify-content: center;">
            <span>猫咪图片</span>
        </div>
        <div class="info">
            <h3>${cat.name}</h3>
            <p><strong>年龄:</strong> ${cat.age}</p>
            <p><strong>性别:</strong> ${cat.gender}</p>
            <p>${cat.description}</p>
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
    const cat = catData.find(c => c.id == catId);
    
    if (!window.authSystem || !window.authSystem.currentUser) {
        alert('请先登录后再申请领养！');
        window.authSystem.openModal('login');
        return;
    }
    
    alert(`感谢您的爱心！您已申请领养 ${cat.name}。我们的工作人员会尽快与您联系。`);
}

// 模拟加载更多功能
function loadMoreCats() {
    console.log('加载更多猫咪信息...');
    // 在实际应用中，这里会从服务器获取更多数据
}