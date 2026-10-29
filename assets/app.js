const API_BASE = '/api/crackscope';
const DIRECT_CAMERA_STREAM = false;

function cameraStreamUrl() {
    return API_BASE + '/camera/stream.mjpg?t=' + Date.now();
}

// ===== UNIFIED PARTICLE FIELD =====
var particleFX = (function() {
    var canvas, ctx, particles = [];
    var mode = 'idle';
    var modeStart = 0;
    var modeDuration = 1000;
    var center = { x: 0, y: 0 };
    var rafId = null;
    var lastTime = 0;

    function rand(min, max) { return min + Math.random() * (max - min); }
    function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

    function resize() {
        if (!canvas) return;
        var dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.floor(window.innerWidth * dpr);
        canvas.height = Math.floor(window.innerHeight * dpr);
        canvas.style.width = window.innerWidth + 'px';
        canvas.style.height = window.innerHeight + 'px';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        center.x = window.innerWidth / 2;
        center.y = window.innerHeight * 0.52;
        seedParticles();
    }

    function seedParticles() {
        var count = Math.max(95, Math.min(180, Math.floor(window.innerWidth * window.innerHeight / 9200)));
        var old = particles.slice();
        particles = [];
        for (var i = 0; i < count; i++) {
            var prev = old[i];
            var bx = rand(24, Math.max(48, window.innerWidth - 24));
            var by = rand(28, Math.max(56, window.innerHeight - 28));
            particles.push({
                x: prev ? prev.x : bx,
                y: prev ? prev.y : by,
                bx: bx,
                by: by,
                sx: prev ? prev.x : bx,
                sy: prev ? prev.y : by,
                size: Math.random() < 0.18 ? 2 : 1,
                alpha: rand(0.32, 0.9),
                speed: rand(0.12, 0.48),
                phase: rand(0, Math.PI * 2),
                color: Math.random() < 0.34 ? '#8dffd0' : '#65ff9f',
            });
        }
    }

    function setMode(nextMode, duration) {
        mode = nextMode;
        modeStart = performance.now();
        modeDuration = duration || 1000;
        particles.forEach(function(p) {
            p.sx = p.x;
            p.sy = p.y;
            if (nextMode === 'emit') {
                p.x = center.x + rand(-8, 8);
                p.y = center.y + rand(-8, 8);
                p.sx = p.x;
                p.sy = p.y;
            }
        });
    }

    function drawCore(now, strength) {
        var pulse = 0.5 + Math.sin(now * 0.005) * 0.5;
        var r = 34 + strength * 22 + pulse * 5;
        ctx.save();
        ctx.globalAlpha = 0.5 + strength * 0.34;
        ctx.fillStyle = '#000';
        ctx.beginPath();
        ctx.arc(center.x, center.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 0.14 + strength * 0.22;
        ctx.strokeStyle = '#65ff9f';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(center.x, center.y, r + 5, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
    }

    function frame(now) {
        if (!ctx) return;
        var dt = Math.min(32, now - (lastTime || now));
        lastTime = now;
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        var progress = clamp((now - modeStart) / modeDuration, 0, 1);
        var ease = 1 - Math.pow(1 - progress, 3);
        var coreStrength = 0;

        particles.forEach(function(p) {
            if (mode === 'absorb') {
                p.x = p.sx + (center.x - p.sx) * ease;
                p.y = p.sy + (center.y - p.sy) * ease;
            } else if (mode === 'emit') {
                p.x = p.sx + (p.bx - p.sx) * ease;
                p.y = p.sy + (p.by - p.sy) * ease;
            } else {
                p.phase += p.speed * dt * 0.001;
                p.x += Math.cos(p.phase) * p.speed * 0.12;
                p.y += Math.sin(p.phase * 0.8) * p.speed * 0.12;
                p.x += (p.bx - p.x) * 0.002;
                p.y += (p.by - p.y) * 0.002;
            }

            var dx = p.x - center.x;
            var dy = p.y - center.y;
            var dist = Math.sqrt(dx * dx + dy * dy);
            var fadeNearCore = mode === 'absorb' ? clamp(dist / 260, 0.12, 1) : 1;
            var alpha = p.alpha * fadeNearCore;
            if (mode === 'emit') alpha *= clamp(progress * 1.4, 0, 1);
            ctx.globalAlpha = alpha;
            ctx.fillStyle = p.color;
            ctx.fillRect(Math.round(p.x), Math.round(p.y), p.size, p.size);
            if (p.size > 1 || mode !== 'idle') {
                ctx.globalAlpha = alpha * 0.28;
                ctx.fillRect(Math.round(p.x - 1), Math.round(p.y - 1), p.size + 2, p.size + 2);
            }
        });
        ctx.globalAlpha = 1;
        if ((mode === 'absorb' || mode === 'emit') && progress >= 1) mode = 'idle';
        rafId = requestAnimationFrame(frame);
    }

    function init() {
        canvas = document.getElementById('particle-canvas');
        if (!canvas) return;
        ctx = canvas.getContext('2d');
        resize();
        window.addEventListener('resize', resize);
        rafId = requestAnimationFrame(frame);
    }

    return {
        init: init,
        absorb: function(duration) { setMode('absorb', duration || 1100); },
        emit: function(duration) { setMode('emit', duration || 900); },
    };
})();

function createPageAssembler() {
    var old = document.querySelector('.page-assembler');
    if (old) old.remove();
    var layer = document.createElement('div');
    layer.className = 'page-assembler';
    var cols = 20, rows = 12;
    var pieceW = window.innerWidth / cols;
    var pieceH = window.innerHeight / rows;
    for (var y = 0; y < rows; y++) {
        for (var x = 0; x < cols; x++) {
            var piece = document.createElement('span');
            piece.className = 'assemble-piece';
            piece.style.setProperty('--x', (x * pieceW + pieceW / 2) + 'px');
            piece.style.setProperty('--y', (y * pieceH + pieceH / 2) + 'px');
            piece.style.setProperty('--pw', Math.ceil(pieceW) + 'px');
            piece.style.setProperty('--ph', Math.ceil(pieceH) + 'px');
            var dist = Math.abs(x - cols / 2) + Math.abs(y - rows / 2);
            piece.style.setProperty('--delay', (dist * 0.012 + Math.random() * 0.05) + 's');
            layer.appendChild(piece);
        }
    }
    document.body.appendChild(layer);
    setTimeout(function() { layer.remove(); }, 1850);
}

// ===== SHATTER TRANSITION =====
function shatterEnterApp(onReveal) {
    var screen = document.getElementById('entry-screen');
    var app = document.getElementById('app-container');
    if (!screen || !app) {
        if (onReveal) onReveal();
        return;
    }

    document.body.classList.add('cracking');
    var rect = screen.getBoundingClientRect();
    var crackOverlay = document.createElement('div');
    crackOverlay.className = 'crack-overlay';
    crackOverlay.style.left = rect.left + 'px';
    crackOverlay.style.top = rect.top + 'px';
    crackOverlay.style.width = rect.width + 'px';
    crackOverlay.style.height = rect.height + 'px';

    var svgNS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('class', 'crack-svg');
    svg.setAttribute('viewBox', '0 0 1000 1000');
    svg.setAttribute('preserveAspectRatio', 'none');

    window._entryCrackPaths = [];
    [
        { x: 260, delay: 0 },
        { x: 500, delay: 0.15 },
        { x: 740, delay: 0.30 },
    ].forEach(function(def) {
        var mainD = generateBeamCrack(def.x, 0, 1000);
        window._entryCrackPaths.push({ d: mainD, x: def.x });
        var path = document.createElementNS(svgNS, 'path');
        path.setAttribute('d', mainD);
        path.setAttribute('class', 'crack-path main-crack');
        path.style.animationDelay = def.delay + 's';
        svg.appendChild(path);

        [0.32, 0.58, 0.78].forEach(function(yFactor, idx) {
            var branch = document.createElementNS(svgNS, 'path');
            var y = Math.round(1000 * yFactor);
            var branchD = generateBranchCrack(def.x, y, 120 + idx * 26, idx % 2 === 0 ? -1 : 1);
            branch.setAttribute('d', branchD);
            branch.setAttribute('class', 'crack-path branch-crack');
            branch.style.animationDelay = (def.delay + 0.18 + idx * 0.08) + 's';
            svg.appendChild(branch);
        });
    });

    crackOverlay.appendChild(svg);
    document.body.appendChild(crackOverlay);
    requestAnimationFrame(function() {
        svg.querySelectorAll('.crack-path').forEach(function(path) {
            path.classList.add('animating');
        });
    });

    setTimeout(function() {
        screen.classList.add('hidden');
        initShowcase();
        navigateTo('background');
        app.classList.add('visible');
        app.classList.add('reveal-page');
        if (onReveal) onReveal();

        createEntryShards(rect);
        crackOverlay.remove();

    }, 1100);

    setTimeout(function() {
        document.querySelectorAll('.shard').forEach(function(shard) { shard.remove(); });
        document.body.classList.remove('cracking');
        app.classList.remove('reveal-page');
    }, 2600);
}

function generateBeamCrack(startX, startY, totalHeight) {
    var segments = 20;
    var segH = totalHeight / segments;
    var x = startX;
    var d = 'M' + x + ',' + startY;
    for (var i = 1; i <= segments; i++) {
        var progress = i / segments;
        var maxJitter = 4 + progress * 38;
        x += (Math.random() - 0.5) * maxJitter * 2;
        x = Math.max(startX - maxJitter * 1.2, Math.min(startX + maxJitter * 1.2, x));
        d += ' L' + Math.round(x) + ',' + Math.round(i * segH);
    }
    return d;
}

function generateBranchCrack(startX, startY, length, direction) {
    var segments = 6;
    var segLen = length / segments;
    var x = startX;
    var y = startY;
    var angle = direction * (0.4 + Math.random() * 0.8);
    var d = 'M' + x + ',' + y;
    for (var i = 1; i <= segments; i++) {
        x += Math.cos(angle) * segLen + (Math.random() - 0.5) * 5;
        y += Math.sin(angle) * segLen + Math.abs(Math.random() - 0.5) * 10;
        d += ' L' + Math.round(x) + ',' + Math.round(y);
    }
    return d;
}

function createEntryShards(rect) {
    var paths = window._entryCrackPaths || [];
    var columns = [];
    var leftEdge = [];
    for (var y = 0; y <= 1000; y += 50) leftEdge.push([0, y]);
    columns.push(leftEdge);
    paths.forEach(function(cp) { columns.push(parseSvgPath(cp.d)); });
    var rightEdge = [];
    for (var y2 = 0; y2 <= 1000; y2 += 50) rightEdge.push([1000, y2]);
    columns.push(rightEdge);

    for (var c = 0; c < columns.length - 1; c++) {
        var clipPts = [];
        columns[c].forEach(function(p) { clipPts.push([p[0] / 1000 * rect.width, p[1] / 1000 * rect.height]); });
        for (var j = columns[c + 1].length - 1; j >= 0; j--) {
            var rp = columns[c + 1][j];
            clipPts.push([rp[0] / 1000 * rect.width, rp[1] / 1000 * rect.height]);
        }

        var shard = document.createElement('div');
        var clipStr = 'polygon(' + clipPts.map(function(p) {
            return Math.round(p[0]) + 'px ' + Math.round(p[1]) + 'px';
        }).join(', ') + ')';
        shard.className = 'shard';
        shard.style.left = rect.left + 'px';
        shard.style.top = rect.top + 'px';
        shard.style.width = rect.width + 'px';
        shard.style.height = rect.height + 'px';
        shard.style.background = 'radial-gradient(ellipse 72% 58% at 50% 50%, rgba(101,255,159,0.08), transparent 74%), #030509';
        shard.style.clipPath = clipStr;
        shard.style.WebkitClipPath = clipStr;
        shard.style.overflow = 'hidden';
        shard.appendChild(createEntryShardTexture());

        var delay = c * 0.12;
        var duration = 0.8 + c * 0.15;
        shard.style.animation = 'shardFall ' + duration + 's ' + delay + 's cubic-bezier(0.3, 0, 0.8, 1) forwards';
        shard.style.setProperty('--fx', ((c - 1.5) * 120 + (Math.random() - 0.5) * 100) + 'px');
        shard.style.setProperty('--fy', (window.innerHeight - rect.top + 250) + 'px');
        shard.style.setProperty('--rx', ((c - 1) * 30 + (Math.random() - 0.5) * 60) + 'deg');
        shard.style.setProperty('--ry', ((Math.random() - 0.5) * 80) + 'deg');
        shard.style.setProperty('--rz', ((c - 1.5) * 35 + (Math.random() - 0.5) * 50) + 'deg');
        document.body.appendChild(shard);
    }
}

function createEntryShardTexture() {
    var texture = document.createElement('div');
    texture.className = 'entry-shard-texture';
    texture.innerHTML = [
        '<div class="entry-shard-title">CRACK<br>SCOPE</div>',
        '<div class="entry-shard-subtitle">BINOCULAR VISION + YOLO SEGMENTATION // CM4 POWERED</div>',
        '<div class="entry-shard-prompt">[ 点击任意位置进入系统 ]</div>'
    ].join('');
    return texture;
}

function parseSvgPath(d) {
    return d.replace(/[ML]\s*/g, '').trim().split(/\s+/).map(function(pair) {
        var xy = pair.split(',');
        return [parseFloat(xy[0]), parseFloat(xy[1])];
    }).filter(function(pt) { return !isNaN(pt[0]) && !isNaN(pt[1]); });
}

// ===== ENTRY ANIMATION =====
(function initEntry() {
    particleFX.init();
    var screen = document.getElementById('entry-screen');
    var titleEl = document.getElementById('entry-title');
    var cornerBadge = document.getElementById('corner-badge');
    var app = document.getElementById('app-container');

    var titleText = 'CRACK\nSCOPE';
    var i = 0;
    function typeTitle() {
        if (i < titleText.length) {
            var c = titleText[i];
            titleEl.textContent = (titleEl.textContent || '') + (c === '\n' ? '\n' : c);
            i++;
            setTimeout(typeTitle, c === '\n' ? 300 : 80 + Math.random() * 60);
        }
    }
    setTimeout(typeTitle, 850);

    // 展示重点：入口页不是直接跳转，而是先触发 warping class。
    // CSS 会把粒子拉伸成“超时空穿梭”效果，动画结束后再进入系统主界面。
    var entering = false;
    screen.addEventListener('click', function() {
        if (entering) return;
        entering = true;
        screen.classList.add('warping');
        particleFX.absorb(1100);
        setTimeout(function() {
            screen.classList.add('hidden');
            initShowcase();
            navigateTo('background');
            app.classList.add('visible');
            if (typeof updateDashStatus === 'function') updateDashStatus('model', 'ready');
            setTimeout(function() {
                if (typeof updateDashStatus === 'function') updateDashStatus('camera', 'online');
                if (typeof toast === 'function') toast('系统就绪', 'success');
            }, 220);
        }, 1160);
    });

    cornerBadge.addEventListener('click', function(event) {
        event.stopPropagation();
        app.classList.remove('visible');
        app.classList.remove('assembling', 'reveal-page');
        screen.classList.remove('hidden', 'warping');
        entering = false;
        particleFX.emit(700);
        navigateTo('background');
        window.scrollTo({ top: 0, behavior: 'instant' });
    });
})();

// ===== NAVIGATION =====
function navigateTo(section) {
    document.querySelectorAll('.section').forEach(function(s) { s.classList.remove('active'); });
    var target = document.getElementById('section-' + section);
    if (target) {
        target.classList.add('active');
        target.classList.remove('section-pop');
        void target.offsetWidth;
        target.classList.add('section-pop');
    }
    document.querySelectorAll('.nav-item').forEach(function(item) {
        var isActive = item.getAttribute('data-section') === section;
        item.classList.toggle('active', isActive);
        if (isActive) {
            item.classList.remove('nav-clicked');
            void item.offsetWidth;
            item.classList.add('nav-clicked');
        }
    });
    if (section === 'showcase') {
        activeCompId = null;
        setTimeout(function() { renderComponentList(); drawShowcaseDevice(); }, 50);
    }
    if (section === 'dashboard') { setTimeout(initChart, 200); updateDashStatus('model', 'ready'); }
    if (section === 'dashboard') { setTimeout(startDeviceStatusLoop, 80); }
    window.scrollTo({ top: 0, behavior: 'instant' });
}

// ===== SHOWCASE =====
var components = [];
var activeCompId = null;

function initShowcase() {
    fetch(API_BASE + '/components')
        .then(function(r) { return r.json(); })
        .then(function(data) { components = data; renderComponentList(); drawShowcaseDevice(); })
        .catch(function() {
            components = [
                {id:'cm4',name:'Raspberry Pi CM4',model:'CM4 2GB Lite WiFi',price:195,desc:'主控单元，运行 YOLO 分割与双目深度计算',icon:'mcu'},
                {id:'board',name:'微雪 CM4 IO 扩展板',model:'CM4-IO-BASE-B',price:79,desc:'提供 USB / TF 卡槽 / 电源接口，连接所有外设',icon:'board'},
                {id:'camera',name:'USB 双目同步相机',model:'400万 1080p 双目',price:210,desc:'左右同步采集图像，用于立体视觉与深度计算',icon:'camera'},
                {id:'tfcard',name:'TF 存储卡',model:'SanDisk 32GB Class10',price:28,desc:'存放 Raspberry Pi OS 系统和 YOLO 模型权重文件',icon:'storage'},
                {id:'heatsink',name:'散热片套件',model:'铝制散热片 + 风扇',price:12,desc:'CM4 长时间推理时主动散热，防止降频',icon:'cooling'},
                {id:'power',name:'充电宝',model:'5V 2A 输出',price:49,desc:'为 CM4 扩展板提供 5V 稳定供电，便携手持',icon:'power'},
            ];
            renderComponentList();
            drawShowcaseDevice();
        });
}

var iconMap = { mcu: 'CPU', board: 'IO', camera: 'CAM', storage: 'TF', cooling: 'FIN', power: '5V' };

function renderComponentList() {
    var list = document.getElementById('component-list');
    if (!list) return;
    list.innerHTML = '';
    components.forEach(function(comp) {
        var isActive = activeCompId === comp.id;
        var card = document.createElement('div');
        card.className = 'component-card' + (isActive ? ' active' : '');
        card.setAttribute('data-id', comp.id);
        card.onclick = function() { selectComponent(comp.id); };
        card.innerHTML =
            '<div class="comp-header">' +
            '<span class="comp-icon">' + (iconMap[comp.icon] || 'MOD') + '</span>' +
            '<span class="comp-name">' + comp.name + '</span>' +
            '</div>' +
            '<div class="comp-model">' + comp.model + '</div>' +
            '<div class="comp-price">¥ ' + comp.price + ' CNY</div>' +
            '<div class="comp-desc">' + (isActive ? comp.desc : comp.desc.substring(0, 28) + '...') + '</div>';
        list.appendChild(card);
    });
}

function selectComponent(id) {
    if (activeCompId === id) {
        // Click same component again -> deselect, show full view
        activeCompId = null;
    } else {
        activeCompId = id;
    }
    renderComponentList();
    drawShowcaseDevice();
    updateHardwarePreview();
}

var showcaseHitboxes = [];
var SHOWCASE_SCALE = 1.16;
var showAllHardwarePreviews = false;
var hardwarePreviewMap = {
    cm4: { src: 'assets/hardware/cm4.png', w: 210, h: 150, left: '13%', top: '65%' },
    board: { src: 'assets/hardware/board.png', w: 220, h: 176, left: '67%', top: '29.4%' },
    camera: { src: 'assets/hardware/camera.png', w: 300, h: 102, left: '35.8%', top: '0.4%' },
    tfcard: { src: 'assets/hardware/tfcard.png', w: 74, h: 52, left: '74%', top: '56%' },
    heatsink: { src: 'assets/hardware/heatsink_h.png', w: 132, h: 94, left: '7.4%', top: '20%' },
    power: { src: 'assets/hardware/power.png', w: 88, h: 168, left: '65%', top: '68%' },
};

function updateHardwarePreview() {
    var panel = document.getElementById('hardware-preview');
    var img = document.getElementById('hardware-preview-img');
    if (!panel || !img) return;
    renderAllHardwarePreviews();
    if (showAllHardwarePreviews) {
        panel.classList.remove('visible');
        img.removeAttribute('src');
        return;
    }
    var cfg = activeCompId ? hardwarePreviewMap[activeCompId] : null;
    if (!cfg) {
        panel.classList.remove('visible');
        img.removeAttribute('src');
        return;
    }
    img.src = cfg.src;
    img.style.width = cfg.w + 'px';
    img.style.height = cfg.h + 'px';
    img.style.transform = cfg.rotate ? 'rotate(' + cfg.rotate + 'deg)' : '';
    panel.style.left = cfg.left;
    panel.style.top = cfg.top;
    panel.classList.add('visible');
}

function renderAllHardwarePreviews() {
    var wrap = document.querySelector('.showcase-canvas-wrap');
    if (!wrap) return;
    var old = wrap.querySelector('.hardware-preview-all');
    if (old) old.remove();
    var btn = document.getElementById('hardware-toggle');
    if (btn) btn.textContent = showAllHardwarePreviews ? 'Hide photos' : 'Show photos';
    if (!showAllHardwarePreviews) return;
    var layer = document.createElement('div');
    layer.className = 'hardware-preview-all';
    Object.keys(hardwarePreviewMap).forEach(function(id) {
        var cfg = hardwarePreviewMap[id];
        var item = document.createElement('div');
        item.className = 'hardware-preview visible';
        item.style.left = cfg.left;
        item.style.top = cfg.top;
        item.innerHTML = '<img src="' + cfg.src + '" alt="">';
        var image = item.querySelector('img');
        image.style.width = cfg.w + 'px';
        image.style.height = cfg.h + 'px';
        image.style.transform = cfg.rotate ? 'rotate(' + cfg.rotate + 'deg)' : '';
        layer.appendChild(item);
    });
    wrap.appendChild(layer);
}

function toggleAllHardwarePreviews() {
    showAllHardwarePreviews = !showAllHardwarePreviews;
    updateHardwarePreview();
}

function bindShowcaseCanvasClick() {
    var canvas = document.getElementById('showcase-canvas');
    if (!canvas || canvas.dataset.bound === '1') return;
    canvas.dataset.bound = '1';
    canvas.addEventListener('click', function(event) {
        var rect = canvas.getBoundingClientRect();
        var x = (event.clientX - rect.left) * canvas.width / rect.width;
        var y = (event.clientY - rect.top) * canvas.height / rect.height;
        x = canvas.width / 2 + (x - canvas.width / 2) / SHOWCASE_SCALE;
        y = canvas.height / 2 + (y - canvas.height / 2) / SHOWCASE_SCALE;
        for (var i = showcaseHitboxes.length - 1; i >= 0; i--) {
            var b = showcaseHitboxes[i];
            if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) {
                // 展示重点：canvas 本身没有 DOM 子元素，所以这里用 hitbox 做点击检测。
                // 点击设备图中的坐标区域后，联动右侧卡片和高亮框。
                selectComponent(b.id);
                return;
            }
        }
    });
}

// ===== 2D PIXEL PCB PLAN DRAWING =====
function drawShowcaseDevice() {
    var canvas = document.getElementById('showcase-canvas');
    if (!canvas) return;
    bindShowcaseCanvasClick();
    var ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(w / 2, h / 2);
    ctx.scale(SHOWCASE_SCALE, SHOWCASE_SCALE);
    ctx.translate(-w / 2, -h / 2);

    // 展示重点：设备构成不是图片，而是用 Canvas 实时绘制的 2D 像素电路平面图。
    // 这样可以根据 activeCompId 动态变暗其他设备、突出当前选中的硬件。
    showcaseHitboxes = [];
    var dimAlpha = activeCompId ? 0.34 : 1;
    var board = { x: 374, y: 250, w: 156, h: 116 };
    var parts = {
        board: { x: board.x, y: board.y, w: board.w, h: board.h, label: 'CM4-IO-BASE-B' },
        cm4: { x: 226, y: 270, w: 116, h: 90, label: 'CM4' },
        heatsink: { x: 244, y: 148, w: 80, h: 58, label: 'HEATSINK' },
        tfcard: { x: 570, y: 364, w: 46, h: 30, label: 'TF CARD' },
        camera: { x: 356, y: 148, w: 188, h: 60, label: 'USB STEREO CAMERA' },
        power: { x: 350, y: 430, w: 204, h: 56, label: '5V POWER BANK' },
    };

    function alphaFor(id) { return activeCompId && activeCompId !== id ? dimAlpha : 1; }
    function rectPath(x, y, rw, rh, color, stroke, alpha) {
        if (x === 34 && y === 26 && rw === w - 68 && rh === h - 52) return;
        ctx.globalAlpha = alpha == null ? 1 : alpha;
        ctx.fillStyle = color;
        ctx.fillRect(x, y, rw, rh);
        ctx.strokeStyle = stroke || '#07160f';
        ctx.lineWidth = 3;
        ctx.strokeRect(x + 1.5, y + 1.5, rw - 3, rh - 3);
        ctx.globalAlpha = 1;
    }
    function pxText(text, x, y, color, size, align, alpha) {
        ctx.globalAlpha = alpha == null ? 1 : alpha;
        ctx.font = (size || 10) + 'px "Press Start 2P", monospace';
        ctx.fillStyle = color || '#e0e8d8';
        ctx.textAlign = align || 'left';
        ctx.textBaseline = 'top';
        ctx.fillText(text, x, y);
        ctx.globalAlpha = 1;
    }
    function pin(x, y, color, alpha) {
        ctx.globalAlpha = alpha == null ? 1 : alpha;
        ctx.fillStyle = color || '#d8c66a';
        ctx.fillRect(x, y, 8, 8);
        ctx.fillStyle = '#07160f';
        ctx.fillRect(x + 2, y + 2, 4, 4);
        ctx.globalAlpha = 1;
    }
    function trace(points, color, widthLine, alpha) {
        ctx.globalAlpha = alpha == null ? 1 : alpha;
        ctx.strokeStyle = color || '#60e7a0';
        ctx.lineWidth = widthLine || 5;
        ctx.lineJoin = 'miter';
        ctx.lineCap = 'square';
        ctx.beginPath();
        ctx.moveTo(points[0][0], points[0][1]);
        for (var i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
        ctx.stroke();
        ctx.globalAlpha = 1;
        points.forEach(function(p) {
            ctx.globalAlpha = alpha == null ? 1 : alpha;
            ctx.fillStyle = color || '#60e7a0';
            ctx.fillRect(p[0] - 4, p[1] - 4, 8, 8);
            ctx.globalAlpha = 1;
        });
    }
    function hit(id, x, y, rw, rh) { showcaseHitboxes.push({ id: id, x: x, y: y, w: rw, h: rh }); }
    function drawTfSlot(alpha, highlight) {
        var sx = board.x + board.w - 58;
        var sy = board.y + board.h - 88;
        rectPath(sx - 6, sy - 6, 52, 54, '#121827', '#808a9a', alpha);
        rectPath(sx, sy, 42, 42, '#0a0d16', highlight || '#5eead4', alpha);
        ctx.globalAlpha = alpha == null ? 1 : alpha;
        ctx.fillStyle = '#101827';
        ctx.fillRect(sx + 6, sy + 6, 30, 30);
        ctx.globalAlpha = 1;
        return { x: sx - 6, y: sy - 6, w: 52, h: 54 };
    }

    // 画 PCB 工作区、网格、走线：模拟嘉立创画板子的俯视图效果。
    rectPath(34, 26, w - 68, h - 52, 'rgba(14,30,23,0.72)', '#285a42', 1);
    trace([[452, 250], [452, 224], [452, 208]], '#55d98e', 5, activeCompId && activeCompId !== 'camera' && activeCompId !== 'board' ? 0.22 : 1);
    trace([[452, 366], [452, 404], [452, 430]], '#e0c15a', 5, activeCompId && activeCompId !== 'power' && activeCompId !== 'board' ? 0.22 : 1);
    trace([[530, 320], [550, 320], [550, 379], [570, 379]], '#5eead4', 4, activeCompId && activeCompId !== 'tfcard' && activeCompId !== 'board' ? 0.22 : 1);
    trace([[342, 315], [374, 315]], '#60e7a0', 4, activeCompId && activeCompId !== 'cm4' && activeCompId !== 'board' ? 0.22 : 1);
    trace([[284, 206], [284, 238], [284, 270]], '#9cff72', 4, activeCompId && activeCompId !== 'heatsink' && activeCompId !== 'cm4' ? 0.22 : 1);

    // IO 扩展板：包括排针、USB 口、TF 卡槽、电源接口等 2D 像素细节。
    var ba = alphaFor('board');
    rectPath(board.x, board.y, board.w, board.h, '#174f91', activeCompId === 'board' ? '#fbb040' : '#5fb9ff', ba);
    rectPath(board.x + 10, board.y + 10, board.w - 20, board.h - 20, '#1d65b8', '#6fc4ff', ba);
    rectPath(board.x + 14, board.y + 16, 34, 22, '#d8d2bd', '#908c82', ba);
    rectPath(board.x + 106, board.y + 14, 34, 24, '#d8d2bd', '#908c82', ba);
    rectPath(board.x + 112, board.y + 72, 30, 28, '#d7d1bf', '#908c82', ba);
    rectPath(board.x + 52, board.y + 56, 48, 24, '#1c2638', '#8390a0', ba);
    for (var i = 0; i < 8; i++) {
        pin(board.x + 18 + i * 15, board.y + 44, '#e2d06b', ba);
        pin(board.x + 18 + i * 15, board.y + 88, '#e2d06b', ba);
    }
    rectPath(board.x + board.w - 40, board.y + 42, 24, 30, '#30364d', '#a0a8b8', ba);
    for (var m = 0; m < 4; m++) {
        var hx = board.x + (m % 2 ? board.w - 24 : 16);
        var hy = board.y + (m > 1 ? board.h - 24 : 16);
        ctx.globalAlpha = ba;
        ctx.fillStyle = '#d8d8d8';
        ctx.fillRect(hx, hy, 12, 12);
        ctx.fillStyle = '#102016';
        ctx.fillRect(hx + 3, hy + 3, 6, 6);
        ctx.globalAlpha = 1;
    }
    hit('board', board.x, board.y, board.w, board.h);

    // CM4 module, connected to the IO board.
    var ca = alphaFor('cm4');
    rectPath(parts.cm4.x, parts.cm4.y, parts.cm4.w, parts.cm4.h, '#2f8a55', activeCompId === 'cm4' ? '#fbb040' : '#88ffc0', ca);
    rectPath(parts.cm4.x + 12, parts.cm4.y + 12, 30, 28, '#1a2330', '#7b8794', ca);
    rectPath(parts.cm4.x + 64, parts.cm4.y + 12, 38, 26, '#20293a', '#7b8794', ca);
    rectPath(parts.cm4.x + 48, parts.cm4.y + 46, 30, 28, '#d7d1bf', '#908c82', ca);
    ctx.globalAlpha = ca;
    ctx.fillStyle = '#e9cf55';
    ctx.fillRect(parts.cm4.x + 8, parts.cm4.y + 8, 9, 9);
    ctx.fillRect(parts.cm4.x + parts.cm4.w - 17, parts.cm4.y + 8, 9, 9);
    ctx.fillRect(parts.cm4.x + 8, parts.cm4.y + parts.cm4.h - 17, 9, 9);
    ctx.fillRect(parts.cm4.x + parts.cm4.w - 17, parts.cm4.y + parts.cm4.h - 17, 9, 9);
    ctx.globalAlpha = 1;
    for (var p = 0; p < 10; p++) pin(parts.cm4.x + 9 + p * 10, parts.cm4.y + 70, '#c6b95e', ca);
    hit('cm4', parts.cm4.x, parts.cm4.y, parts.cm4.w, parts.cm4.h);

    // Heatsink: top-down aluminum fins.
    var ha = alphaFor('heatsink');
    rectPath(parts.heatsink.x, parts.heatsink.y, parts.heatsink.w, parts.heatsink.h, '#a5a9a6', activeCompId === 'heatsink' ? '#fbb040' : '#d8d8d8', ha);
    for (var f = 0; f < 6; f++) {
        ctx.globalAlpha = ha;
        ctx.fillStyle = f % 2 ? '#747b78' : '#c5cac6';
        ctx.fillRect(parts.heatsink.x + 8 + f * 11, parts.heatsink.y + 7, 6, parts.heatsink.h - 14);
        ctx.globalAlpha = 1;
    }
    hit('heatsink', parts.heatsink.x, parts.heatsink.y, parts.heatsink.w, parts.heatsink.h);

    // TF card: external storage block connected to the IO board.
    var ta = alphaFor('tfcard');
    var tfX = parts.tfcard.x;
    rectPath(tfX, parts.tfcard.y, parts.tfcard.w, parts.tfcard.h, '#183927', activeCompId === 'tfcard' ? '#65ff9f' : '#8dffd0', ta);
    rectPath(tfX + 5, parts.tfcard.y + 5, 34, 9, '#0c1812', '#65ff9f', ta);
    for (var gp = 0; gp < 4; gp++) {
        ctx.globalAlpha = ta;
        ctx.fillStyle = '#9cff72';
        ctx.fillRect(tfX + 7 + gp * 8, parts.tfcard.y + 20, 5, 6);
        ctx.globalAlpha = 1;
    }
    hit('tfcard', tfX, parts.tfcard.y, parts.tfcard.w, parts.tfcard.h);

    // Stereo camera: two high-detail pixel lenses and ribbon/USB connector.
    var camA = alphaFor('camera');
    rectPath(parts.camera.x, parts.camera.y, parts.camera.w, parts.camera.h, '#2b2d35', activeCompId === 'camera' ? '#fbb040' : '#5eead4', camA);
    rectPath(parts.camera.x + 12, parts.camera.y + 12, parts.camera.w - 24, parts.camera.h - 24, '#383b46', '#767f8c', camA);
    function lens(cx, cy) {
        ctx.globalAlpha = camA;
        ctx.fillStyle = '#121426';
        ctx.fillRect(cx - 23, cy - 23, 46, 46);
        ctx.fillStyle = '#232a58';
        ctx.fillRect(cx - 17, cy - 17, 34, 34);
        ctx.fillStyle = '#111827';
        ctx.fillRect(cx - 10, cy - 10, 20, 20);
        ctx.fillStyle = '#71e4ff';
        ctx.fillRect(cx - 7, cy - 7, 5, 5);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(cx - 1, cy - 10, 3, 3);
        ctx.strokeStyle = '#60e7a0';
        ctx.lineWidth = 3;
        ctx.strokeRect(cx - 24.5, cy - 24.5, 49, 49);
        ctx.globalAlpha = 1;
    }
    lens(parts.camera.x + 50, parts.camera.y + 30);
    lens(parts.camera.x + 138, parts.camera.y + 30);
    rectPath(parts.camera.x + 86, parts.camera.y + 22, 24, 18, '#10131e', '#8992a8', camA);
    hit('camera', parts.camera.x, parts.camera.y, parts.camera.w, parts.camera.h);

    // Power bank: flat rectangle with USB-A output and battery cells.
    var pa = alphaFor('power');
    rectPath(parts.power.x, parts.power.y, parts.power.w, parts.power.h, '#685f3b', activeCompId === 'power' ? '#fbb040' : '#d8c66a', pa);
    rectPath(parts.power.x + 14, parts.power.y + 12, 62, 32, '#777052', '#cfc07a', pa);
    rectPath(parts.power.x + 152, parts.power.y + 16, 34, 24, '#222838', '#a0a8b8', pa);
    for (var led = 0; led < 4; led++) {
        ctx.globalAlpha = pa;
        ctx.fillStyle = led < 3 ? '#60e7a0' : '#304033';
        ctx.fillRect(parts.power.x + 92 + led * 14, parts.power.y + 26, 7, 7);
        ctx.globalAlpha = 1;
    }
    hit('power', parts.power.x, parts.power.y, parts.power.w, parts.power.h);

    if (activeCompId) {
        var pbox = parts[activeCompId];
        if (activeCompId === 'tfcard') pbox = parts.tfcard;
        var t = Date.now() % 1000;
        if (pbox && t < 700) {
            ctx.strokeStyle = '#fbb040';
            ctx.lineWidth = 5;
            ctx.strokeRect(pbox.x - 8, pbox.y - 8, pbox.w + 16, pbox.h + 16);
            ctx.fillStyle = '#fbb040';
            ctx.fillRect(pbox.x - 16, pbox.y - 16, 14, 4);
            ctx.fillRect(pbox.x - 16, pbox.y - 16, 4, 14);
            ctx.fillRect(pbox.x + pbox.w + 2, pbox.y + pbox.h + 12, 14, 4);
            ctx.fillRect(pbox.x + pbox.w + 12, pbox.y + pbox.h + 2, 4, 14);
        }
    }
    ctx.restore();
    updateHardwarePreview();
}

// ===== DASHBOARD =====
var widthChart = null;
var streamRunning = false;
var streamTimer = null;
var previewRunning = false;
var previewTimer = null;
var captureBusy = false;
var captureFrozen = false;
var photoData = null;
var showingMask = true;
var recordId = 0;
var statsData = { count: 0, sum: 0, max: -Infinity, min: Infinity };
var wsConnection = null;
var useWs = true;
var previewLoading = false;
var deviceStatusTimer = null;
var lastDeviceResultId = 0;
var offlineIndex = 0;
var offlineCount = 10;
var DEMO_MODE = false;

function updateDemoModeButton() {
    var btn = document.getElementById('btn-demo-mode');
    if (!btn) return;
    btn.classList.toggle('active', DEMO_MODE);
    btn.setAttribute('aria-pressed', DEMO_MODE ? 'true' : 'false');
    var text = btn.querySelector('.demo-switch-text');
    if (text) text.textContent = DEMO_MODE ? '演示' : 'CM4';
}

function toggleDemoMode() {
    DEMO_MODE = !DEMO_MODE;
    stopCameraPreview();
    setCameraFrozen(false);
    clearCameraImage();
    updateDemoModeButton();
    updateDashStatus('camera', DEMO_MODE ? 'offline' : 'online');
    updateDashStatus('stream', 'idle');
    updateCameraPlaceholders(false);
    toast(DEMO_MODE ? '演示模式：只显示离线样例' : '连接模式：直接走相机预览', 'success');
}

function updateDashStatus(type, state) {
    var map = {
        camera: { dot: 'dot-camera', txt: 'txt-camera' },
        model: { dot: 'dot-model', txt: 'txt-model' },
        stream: { dot: 'dot-stream', txt: 'txt-stream' },
    };
    var el = map[type];
    if (!el) return;
    var dot = document.getElementById(el.dot);
    var txt = document.getElementById(el.txt);
    if (!dot || !txt) return;
    dot.className = 'status-dot ' + state;
    var labels = {
        camera: { offline: '设备未上线', online: 'CM4 设备在线' },
        model: { offline: '模型未加载', loading: '模型加载中...', ready: 'YOLO 模型就绪' },
        stream: { idle: '检测空闲', running: '相机预览中', capture: '拍照检测中' },
    };
    txt.textContent = labels[type][state];
}

async function refreshCameraStatus() {
    try {
        var resp = await fetch(API_BASE + '/device/status');
        var data = await resp.json();
        updateDashStatus('camera', data.online ? 'online' : 'offline');
        updateCameraPlaceholders(data.online);
        if (data.latest_result && data.latest_result.id && data.latest_result.id !== lastDeviceResultId) {
            lastDeviceResultId = data.latest_result.id;
            if (data.latest_result.kind === 'capture' && data.latest_result.payload) {
                applyDevicePayload(data.latest_result.payload, false);
            }
        }
    } catch (e) {
        updateDashStatus('camera', 'offline');
        updateCameraPlaceholders(false);
    }
}

function startDeviceStatusLoop() {
    if (DEMO_MODE) {
        updateDashStatus('camera', 'offline');
        updateCameraPlaceholders(false);
        return;
    }
    if (deviceStatusTimer) return;
    var loop = function() {
        refreshCameraStatus().finally(function() {
            deviceStatusTimer = setTimeout(loop, 1200);
        });
    };
    loop();
}

function updateCameraPlaceholders(connected) {
    var leftPh = document.getElementById('cam-left-ph');
    if (leftPh) {
        var leftText = leftPh.querySelector('div:last-child, span:last-child');
        if (leftText) leftText.textContent = connected ? '相机已连接' : '等待相机连接';
    }
}

async function loadCameraPreview() {
    if (previewLoading || streamRunning) return;
    previewLoading = true;
    try {
        await fetch(API_BASE + '/stream/start', { method: 'POST' });
        var resp = await fetch(API_BASE + '/stream/frame');
        var data = await resp.json();
        if (!data.error) {
            handleStreamData(data);
            updateDashStatus('stream', 'idle');
        }
    } catch (e) {
        // Keep placeholders visible if the preview frame fails.
    } finally {
        fetch(API_BASE + '/stream/stop', { method: 'POST' }).catch(function() {});
        previewLoading = false;
    }
}

function toggleCameraPreview() {
    if (previewRunning) {
        stopCameraPreview();
    } else {
        startCameraPreview();
    }
}

async function startCameraPreview() {
    if (previewRunning) return;
    var btn = document.getElementById('btn-camera-preview');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Opening...';
    }
    if (DEMO_MODE) {
        previewRunning = true;
        if (btn) {
            btn.disabled = false;
            btn.textContent = '[CAM] Close demo';
            btn.classList.add('running');
        }
        updateDashStatus('camera', 'offline');
        updateDashStatus('stream', 'running');
        await loadOfflinePreview();
        return;
    }
    try {
        if (DIRECT_CAMERA_STREAM) {
            var leftImg = document.getElementById('cam-left-img');
            var leftPh = document.getElementById('cam-left-ph');
            previewRunning = true;
            if (leftImg) {
                leftImg.src = cameraStreamUrl();
                leftImg.hidden = false;
                leftImg.style.setProperty('display', 'block', 'important');
                leftImg.style.visibility = 'visible';
                leftImg.style.opacity = '1';
                leftImg.style.zIndex = '2';
            }
            if (leftPh) leftPh.style.display = 'none';
            if (btn) {
                btn.disabled = false;
                btn.textContent = '[CAM] Close camera';
                btn.classList.add('running');
            }
            updateDashStatus('stream', 'running');
            updateDashStatus('camera', 'online');
            toast('Live stream opened', 'success');
            return;
        }
        var statusResp = await fetch(API_BASE + '/device/status');
        var statusData = await statusResp.json();
        if (!statusData || !statusData.online) {
            previewRunning = false;
            if (btn) {
                btn.disabled = false;
                btn.textContent = '[CAM] Open camera';
                btn.classList.remove('running');
            }
            updateDashStatus('camera', 'offline');
            updateDashStatus('stream', 'idle');
            clearCameraImage();
            toast('CM4 offline: turn on demo to use offline samples', 'error');
            return;
        }
        var resp = await fetch(API_BASE + '/device/command/camera_on', { method: 'POST' });
        var data = await resp.json();
        if (!data.success) throw new Error('preview start failed');
        previewRunning = true;
        if (btn) {
            btn.disabled = false;
            btn.textContent = '[CAM] Close camera';
            btn.classList.add('running');
        }
        updateDashStatus('stream', 'running');
        updateDashStatus('camera', 'online');
        startDeviceStatusLoop();
        clearCameraImage('Waiting for live preview');
        pollDevicePreview();
        toast('Camera command sent, waiting for live preview', 'success');
    } catch (e) {
        previewRunning = false;
        if (btn) {
            btn.disabled = false;
            btn.textContent = '[CAM] Open camera';
            btn.classList.remove('running');
        }
        updateDashStatus('stream', 'idle');
        clearCameraImage();
        toast('Open camera failed in CM4 mode', 'error');
    }
}

function pollDevicePreview() {
    if (DEMO_MODE) return;
    if (!previewRunning || captureBusy || captureFrozen) return;
    fetch(API_BASE + '/device/result/latest?kind=preview')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var result = data && data.result;
            if (result && result.payload && result.payload.images) {
                showCameraImages(result.payload);
                updateResultPanel(result.payload);
            }
        })
        .catch(function() {})
        .finally(function() {
            if (previewRunning && !captureBusy && !captureFrozen) {
                previewTimer = setTimeout(pollDevicePreview, 100);
            }
        });
}

function stopCameraPreview() {
    previewRunning = false;
    if (previewTimer) {
        clearTimeout(previewTimer);
        previewTimer = null;
    }
    if (DIRECT_CAMERA_STREAM) {
        var liveImg = document.getElementById('cam-left-img');
        if (liveImg) liveImg.removeAttribute('src');
    } else if (!DEMO_MODE) {
        fetch(API_BASE + '/device/command/camera_off', { method: 'POST' }).catch(function() {});
    }
    var btn = document.getElementById('btn-camera-preview');
    if (btn) {
        btn.disabled = false;
        btn.textContent = '[CAM] Open camera';
        btn.classList.remove('running');
    }
    updateDashStatus('stream', 'idle');
    toast(DEMO_MODE ? 'Demo preview closed' : '已发送关闭摄像头命令', 'success');
}

updateDemoModeButton();

function pollCameraPreview() {
    if (!previewRunning || captureBusy || captureFrozen) return;
    fetch(API_BASE + '/camera/preview/frame')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data && data.success && data.images) {
                showCameraImages(data);
            }
        })
        .catch(function() {})
        .finally(function() {
            if (previewRunning && !captureBusy && !captureFrozen) {
                previewTimer = setTimeout(pollCameraPreview, 120);
            }
        });
}

async function freezeDirectStreamFrame() {
    if (!DIRECT_CAMERA_STREAM || !previewRunning) return;
    try {
        var resp = await fetch(API_BASE + '/camera/preview/frame?freeze=' + Date.now());
        if (!resp.ok) return;
        var data = await resp.json();
        if (data && data.success && data.images) {
            var wasFrozen = captureFrozen;
            captureFrozen = false;
            showCameraImages(data);
            captureFrozen = wasFrozen;
            updateResultPanel(data);
        }
    } catch (e) {
        // If freezing fails, detection still proceeds and will replace the stream with the result.
    }
}

function updateResultPanel(data) {
    if (!data || !data.result) return;
    var result = data.result;
    var width = Number(result.width_mm || 0);
    var confidence = Number(result.confidence || 0);
    var inferenceMs = result.inference_ms == null ? '--' : result.inference_ms;
    var isCameraPreview = data.source === 'camera' && width === 0;
    var widthEl = document.getElementById('width-val');
    var confEl = document.getElementById('conf-val');
    var infEl = document.getElementById('inf-val');
    if (widthEl) widthEl.textContent = isCameraPreview ? '--' : width.toFixed(2);
    if (confEl) confEl.textContent = isCameraPreview ? 'CAM' : (confidence * 100).toFixed(1) + '%';
    if (infEl) infEl.textContent = inferenceMs + ' ms';
    var detail = document.querySelector('.result-detail');
    if (detail && data.source === 'camera') {
        var distance = result.distance_mm == null ? '--' : Number(result.distance_mm).toFixed(0) + ' mm';
        var message = result.message || '真实双目相机预览';
        var primarySide = result.primary_side === 'right' ? '右目' : '左目';
        detail.innerHTML =
            '<div>状态: <span>' + message + '</span></div>' +
            '<div>主结果: <span>' + primarySide + '</span></div>' +
            '<div>距离: <span>' + distance + '</span></div>' +
            '<div>耗时: <span id="inf-val">' + inferenceMs + ' ms</span></div>';
    }
}

function imageDataUrl(data, key) {
    if (!data || !data.images || !data.images[key]) {
        throw new Error('missing image: ' + key);
    }
    var fmt = data.image_format === 'jpeg' ? 'jpeg' : 'png';
    return 'data:image/' + fmt + ';base64,' + data.images[key];
}

function setCaptureActionButtons(frozen) {
    ['btn-save-capture', 'btn-next-capture'].forEach(function(id) {
        var btn = document.getElementById(id);
        if (!btn) return;
        btn.disabled = !frozen;
        btn.classList.toggle('mode-hidden', !frozen);
    });
}

function setCameraFrozen(frozen) {
    captureFrozen = frozen;
    ['cam-left-panel'].forEach(function(id) {
        var panel = document.getElementById(id);
        if (panel) panel.classList.toggle('frozen', frozen);
    });
    hideWidthTooltip('left');
    setCaptureActionButtons(frozen);
}

function hideWidthTooltip(side) {
    var tip = document.getElementById(side === 'right' ? 'tip-right' : 'tip-left');
    if (tip) tip.classList.remove('visible');
}

function imagePointFromEvent(event, img) {
    var rect = img.getBoundingClientRect();
    if (!img.naturalWidth || !img.naturalHeight || rect.width <= 0 || rect.height <= 0) return null;
    var imageAspect = img.naturalWidth / img.naturalHeight;
    var boxAspect = rect.width / rect.height;
    var drawW = rect.width;
    var drawH = rect.height;
    var offX = 0;
    var offY = 0;
    if (boxAspect > imageAspect) {
        drawW = rect.height * imageAspect;
        offX = (rect.width - drawW) / 2;
    } else {
        drawH = rect.width / imageAspect;
        offY = (rect.height - drawH) / 2;
    }
    var xIn = event.clientX - rect.left - offX;
    var yIn = event.clientY - rect.top - offY;
    if (xIn < 0 || yIn < 0 || xIn > drawW || yIn > drawH) return null;
    return {
        imageX: xIn / drawW * img.naturalWidth,
        imageY: yIn / drawH * img.naturalHeight,
        panelX: event.clientX - img.closest('.camera-panel').getBoundingClientRect().left,
        panelY: event.clientY - img.closest('.camera-panel').getBoundingClientRect().top,
    };
}

function nearestWidthPoint(side, imageX, imageY) {
    if (!photoData || !photoData.width_points) return null;
    var points = photoData.width_points[side] || [];
    var best = null;
    var bestD = Infinity;
    points.forEach(function(point) {
        var dx = Number(point.x) - imageX;
        var dy = Number(point.y) - imageY;
        var d = Math.sqrt(dx * dx + dy * dy);
        if (d < bestD) {
            best = point;
            bestD = d;
        }
    });
    return bestD <= 80 ? best : null;
}

function handleWidthHover(side, event) {
    if (!captureFrozen || !showingMask) return hideWidthTooltip(side);
    var img = document.getElementById(side === 'right' ? 'cam-right-img' : 'cam-left-img');
    var tip = document.getElementById(side === 'right' ? 'tip-right' : 'tip-left');
    if (!img || !tip) return;
    var pos = imagePointFromEvent(event, img);
    if (!pos) return hideWidthTooltip(side);
    var point = nearestWidthPoint(side, pos.imageX, pos.imageY);
    if (!point) return hideWidthTooltip(side);
    var mm = Number(point.width_mm || 0);
    var px = Number(point.width_px || 0);
    tip.innerHTML = '<div>' + (mm ? mm.toFixed(3) + ' mm' : px.toFixed(2) + ' px') + '</div><div>x ' + Math.round(point.x) + ', y ' + Math.round(point.y) + '</div>';
    tip.style.left = Math.min(pos.panelX + 14, img.parentElement.clientWidth - 118) + 'px';
    tip.style.top = Math.max(8, pos.panelY - 42) + 'px';
    tip.classList.add('visible');
}

function bindWidthHover() {
    [
        { side: 'left', panel: 'cam-left-panel' },
    ].forEach(function(item) {
        var panel = document.getElementById(item.panel);
        if (!panel || panel.dataset.widthHover === '1') return;
        panel.dataset.widthHover = '1';
        panel.addEventListener('mousemove', function(event) { handleWidthHover(item.side, event); });
        panel.addEventListener('mouseleave', function() { hideWidthTooltip(item.side); });
    });
}

// ===== PHOTO CAPTURE =====
async function doCapture() {
    var btn = document.getElementById('btn-capture');
    if (!btn || captureBusy) return;
    captureBusy = true;
    if (previewTimer) {
        clearTimeout(previewTimer);
        previewTimer = null;
    }
    btn.disabled = true;
    btn.textContent = 'Detecting...';
    btn.classList.add('running');
    updateDashStatus('stream', 'capture');

    try {
        if (DEMO_MODE) {
            var demoData = await loadOfflineSample(true, false, offlineIndex);
            if (!demoData) throw new Error('offline sample unavailable');
            return;
        }
        if (DIRECT_CAMERA_STREAM) {
            await freezeDirectStreamFrame();
            setCameraFrozen(true);
            var directResp = await fetch(API_BASE + '/capture', { method: 'POST' });
            if (!directResp.ok) {
                var directErr = await directResp.text().catch(function() { return ''; });
                throw new Error('HTTP ' + directResp.status + (directErr ? ': ' + directErr.slice(0, 80) : ''));
            }
            var directData = await directResp.json();
            applyDevicePayload(directData, true);
            return;
        }
        var statusResp = await fetch(API_BASE + '/device/status');
        var statusData = await statusResp.json();
        if (!statusData || !statusData.online) {
            toast('CM4 offline: turn on demo to use offline samples', 'error');
            return;
        }
        var resp = await fetch(API_BASE + '/device/command/capture', { method: 'POST' });
        if (!resp.ok) {
            var errText = await resp.text().catch(function() { return ''; });
            throw new Error('HTTP ' + resp.status + (errText ? ': ' + errText.slice(0, 80) : ''));
        }
        var ack = await resp.json();
        if (ack.success && ack.command) {
            toast('拍照命令已发送，等待 CM4 回传...', 'success');
            var data = await waitForDeviceCapture(ack.command.id, 30000);
            applyDevicePayload(data, true);
        } else {
            throw new Error(ack.error || '后端返回失败');
        }
    } catch (e) {
        console.error('capture failed', e);
        toast(DEMO_MODE ? 'Offline sample load failed' : 'CM4 capture failed', 'error');
    } finally {
        captureBusy = false;
        btn.disabled = false;
        btn.textContent = '[CAP] Detect';
        btn.classList.remove('running');
        if (previewRunning && !captureFrozen) {
            updateDashStatus('stream', 'running');
            if (!DEMO_MODE && !DIRECT_CAMERA_STREAM) previewTimer = setTimeout(pollDevicePreview, 100);
        } else if (captureFrozen) {
            updateDashStatus('stream', 'idle');
        } else {
            updateDashStatus('stream', 'idle');
        }
    }
}

async function loadOfflinePreview() {
    offlineIndex = 0;
    setCameraFrozen(false);
    photoData = null;
    showingMask = true;
    var viewBtn = document.getElementById('btn-toggle-view');
    if (viewBtn) {
        viewBtn.disabled = true;
        viewBtn.classList.add('mode-hidden');
        viewBtn.textContent = '[VIEW] Toggle view';
    }
    return loadOfflineSample(false, false, offlineIndex);
}

async function refreshOfflineCount() {
    try {
        var resp = await fetch(API_BASE + '/offline/list');
        if (!resp.ok) return offlineCount;
        var data = await resp.json();
        if (data && data.count) offlineCount = Number(data.count) || offlineCount;
    } catch (e) {}
    return offlineCount;
}

// Offline demo data cache
var _offlineCache = null;
async function _loadOfflineCache() {
    if (_offlineCache) return _offlineCache;
    var resp = await fetch('assets/offline_data.json');
    if (!resp.ok) throw new Error('Failed to load offline data');
    _offlineCache = await resp.json();
    offlineCount = _offlineCache.length;
    return _offlineCache;
}

async function loadOfflineSample(freeze, announce, index) {
    try {
        var cache = await _loadOfflineCache();
        if (!cache || !cache.length) throw new Error('Cache empty');
        if (index == null) {
            index = offlineIndex % cache.length;
            offlineIndex = (offlineIndex + 1) % cache.length;
        }
        var data = cache[index % cache.length];
        if (!data || !data.success) throw new Error('Bad entry');
        if (data.offline_index != null) offlineIndex = Number(data.offline_index);
        if (freeze) {
            applyDevicePayload(data, announce);
        } else {
            showCameraRawPreview(data);
            updateResultPanel(data);
        }
        return data;
    } catch (e) {
        console.error('[demo]', e.message);
        return null;
    }
}

function applyDevicePayload(data, announce) {
    if (!data || !data.success) return;
    photoData = data;
    showingMask = true;
    setCameraFrozen(true);
    showPhotoResult(data, 'mask');
    var viewBtn = document.getElementById('btn-toggle-view');
    if (viewBtn) {
        viewBtn.disabled = false;
        viewBtn.classList.remove('mode-hidden');
        viewBtn.textContent = '[VIEW] Raw';
    }
    updateResultPanel(data);
    var width = data.result && data.result.width_mm != null ? Number(data.result.width_mm) : 0;
    addChartPoint(width);
    addTableRow(width, data.result ? data.result.confidence : 0, 'DEVICE');
    updateStats(width);
    if (announce) toast('CM4 回传完成: ' + width.toFixed(2) + ' mm', 'success');
}

function waitForDeviceCapture(commandId, timeoutMs) {
    var started = Date.now();
    return new Promise(function(resolve, reject) {
        function poll() {
            fetch(API_BASE + '/device/result/latest?kind=capture')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var result = data && data.result;
                    if (result && result.command_id === commandId && result.payload) {
                        lastDeviceResultId = result.id;
                        resolve(result.payload);
                        return;
                    }
                    if (Date.now() - started > timeoutMs) {
                        reject(new Error('等待 CM4 回传超时'));
                        return;
                    }
                    setTimeout(poll, 900);
                })
                .catch(function() {
                    if (Date.now() - started > timeoutMs) {
                        reject(new Error('等待 CM4 回传超时'));
                    } else {
                        setTimeout(poll, 1200);
                    }
                });
        }
        poll();
    });
}

function showPhotoResult(data, type) {
    var key = type === 'mask' ? 'mask' : 'raw';
    setCameraImage(data, 'left_' + key);
}

function showCameraImages(data) {
    if (captureFrozen) return;
    setCameraImage(data, 'left_mask');
}

function showCameraRawPreview(data) {
    if (captureFrozen) return;
    setCameraImage(data, 'left_raw');
}

function setCameraImage(data, key) {
    var leftImg = document.getElementById('cam-left-img');
    var leftPh = document.getElementById('cam-left-ph');
    if (!leftImg) return;
    leftImg.src = imageDataUrl(data, key);
    leftImg.hidden = false;
    leftImg.style.setProperty('display', 'block', 'important');
    leftImg.style.visibility = 'visible';
    leftImg.style.opacity = '1';
    leftImg.style.zIndex = '2';
    if (leftPh) leftPh.style.display = 'none';
    var panel = document.getElementById('cam-left-panel');
    if (panel) panel.style.cursor = 'zoom-in';
}

function clearCameraImage(message) {
    var leftImg = document.getElementById('cam-left-img');
    var leftPh = document.getElementById('cam-left-ph');
    if (leftImg) {
        leftImg.removeAttribute('src');
        leftImg.style.display = 'none';
        leftImg.style.visibility = 'hidden';
    }
    if (leftPh) {
        leftPh.style.display = 'flex';
        var text = leftPh.querySelector('span:last-child');
        if (text) text.textContent = message || 'Waiting for camera';
    }
}

function togglePhotoView() {
    if (!photoData) return;
    showingMask = !showingMask;
    showPhotoResult(photoData, showingMask ? 'mask' : 'raw');
    hideWidthTooltip('left');
    document.getElementById('btn-toggle-view').textContent = showingMask ? '[VIEW] Raw' : '[VIEW] Overlay';
}

async function saveCaptureResult() {
    if (!photoData) return;
    var btn = document.getElementById('btn-save-capture');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Saving...';
    }
    try {
        var resp = await fetch(API_BASE + '/capture/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(photoData),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var blob = await resp.blob();
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'crackscope_' + new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19) + '.zip';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        toast('已下载检测结果', 'success');
    } catch (e) {
        console.error('save failed', e);
        toast('保存失败: ' + (e && e.message ? e.message : '未知错误'), 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '[SAVE] Save';
        }
    }
}

async function nextCapture() {
    photoData = null;
    showingMask = true;
    setCameraFrozen(false);
    var viewBtn = document.getElementById('btn-toggle-view');
    if (viewBtn) {
        viewBtn.disabled = true;
        viewBtn.classList.add('mode-hidden');
        viewBtn.textContent = '[VIEW] Toggle view';
    }
    updateDashStatus('stream', previewRunning ? 'running' : 'idle');
    if (!DEMO_MODE) {
        if (DIRECT_CAMERA_STREAM && previewRunning) {
            var liveImg = document.getElementById('cam-left-img');
            var livePh = document.getElementById('cam-left-ph');
            if (liveImg) {
                liveImg.src = cameraStreamUrl();
                liveImg.hidden = false;
                liveImg.style.setProperty('display', 'block', 'important');
                liveImg.style.visibility = 'visible';
            }
            if (livePh) livePh.style.display = 'none';
        } else {
            clearCameraImage(previewRunning ? 'Waiting for live preview' : 'Waiting for camera');
            if (previewRunning) pollDevicePreview();
        }
        toast('Ready for next CM4 capture', 'success');
        return;
    }
    await refreshOfflineCount();
    offlineIndex = (offlineIndex + 1) % Math.max(1, offlineCount);
    var data = await loadOfflineSample(true, false, offlineIndex);
    if (data) toast('已切换下一张离线样例', 'success');
}

// ===== STREAM =====
function toggleStream() {
    if (streamRunning) { stopStream(); } else { startStream(); }
}

async function startStream() {
    // 实时检测先通知后端启动流，再优先使用 WebSocket 获取连续帧。
    try { await fetch(API_BASE + '/stream/start', { method: 'POST' }); } catch (e) {}
    streamRunning = true;
    var btn = document.getElementById('btn-stream-toggle');
    if (btn) { btn.textContent = '[STOP] Stop'; btn.classList.add('running'); }
    updateDashStatus('stream', 'running');
    var lph = document.getElementById('cam-left-ph');
    if (lph) lph.style.display = 'none';
    if (useWs) { connectWS(); } else { pollStream(); }
    toast('实时检测已启动', 'success');
}

function stopStream() {
    streamRunning = false;
    if (streamTimer) { clearTimeout(streamTimer); streamTimer = null; }
    if (wsConnection) { try { wsConnection.send('stop'); wsConnection.close(); } catch (e) {} wsConnection = null; }
    fetch(API_BASE + '/stream/stop', { method: 'POST' }).catch(function() {});
    var btn = document.getElementById('btn-stream-toggle');
    if (btn) { btn.textContent = '[LIVE] Start'; btn.classList.remove('running'); }
    updateDashStatus('stream', 'idle');
    toast('实时检测已停止', 'success');
}

function connectWS() {
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsConnection = new WebSocket(proto + '//' + location.host + API_BASE + '/ws/stream');
    wsConnection.onopen = function() { wsConnection.send('start'); };
    wsConnection.onmessage = function(e) { handleStreamData(JSON.parse(e.data)); };
    wsConnection.onerror = function() { useWs = false; wsConnection = null; if (streamRunning) pollStream(); };
    wsConnection.onclose = function() { wsConnection = null; if (streamRunning) { useWs = false; pollStream(); } };
}

function pollStream() {
    // WebSocket 失败时降级为 HTTP 轮询，保证部署环境不支持 WS 时页面仍可演示。
    if (!streamRunning) return;
    fetch(API_BASE + '/stream/frame')
        .then(function(r) { return r.json(); })
        .then(function(data) { if (!data.error) handleStreamData(data); })
        .catch(function() {});
    streamTimer = setTimeout(pollStream, 300);
}

function handleStreamData(data) {
    if (!data.images) return;
    setCameraImage(data, 'left_mask');
    if (data.result) {
        updateResultPanel(data);
        var autoRec = document.getElementById('toggle-auto-record');
        var checked = autoRec && autoRec.querySelector('.toggle-box').classList.contains('checked');
        if (checked && !(data.source === 'camera' && data.result.width_mm === 0)) {
            addChartPoint(data.result.width_mm);
            addTableRow(data.result.width_mm, data.result.confidence, 'STREAM');
            updateStats(data.result.width_mm);
        }
    }
}

// ===== CHART =====
function initChart() {
    var canvas = document.getElementById('width-chart');
    if (!canvas || widthChart) return;
    var ctx = canvas.getContext('2d');
    widthChart = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [{
            label: '裂缝宽度 mm',
            data: [],
            borderColor: '#60e7a0',
            backgroundColor: 'rgba(96,231,160,0.06)',
            borderWidth: 2, pointRadius: 0, pointHoverRadius: 4,
            pointHoverBackgroundColor: '#60e7a0',
            tension: 0.2, fill: true
        }] },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: { duration: 200 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(12,12,18,0.95)',
                    titleColor: '#e0e8d8', bodyColor: '#60e7a0',
                    borderColor: '#3a3a4a', borderWidth: 1,
                    cornerRadius: 0, padding: 10,
                    callbacks: { label: function(c) { return c.parsed.y.toFixed(2) + ' mm'; } }
                }
            },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#3a3a4a', font: { size: 9 }, maxTicksLimit: 6 } },
                y: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#3a3a4a', font: { size: 9 }, callback: function(v) { return v.toFixed(1) + ' mm'; } }, beginAtZero: false, min: 0 }
            }
        }
    });
}

function addChartPoint(width) {
    if (!widthChart) { initChart(); if (!widthChart) return; }
    var now = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    widthChart.data.labels.push(now);
    widthChart.data.datasets[0].data.push(width);
    if (widthChart.data.labels.length > 80) { widthChart.data.labels.shift(); widthChart.data.datasets[0].data.shift(); }
    widthChart.update('none');
    var cnt = document.getElementById('chart-count');
    if (cnt) cnt.textContent = widthChart.data.datasets[0].data.length + ' 条';
}

function clearChartData() {
    if (widthChart) { widthChart.data.labels = []; widthChart.data.datasets[0].data = []; widthChart.update(); }
    var cnt = document.getElementById('chart-count');
    if (cnt) cnt.textContent = '0 条';
    toast('图表已清空', 'success');
}

// ===== TABLE =====
function addTableRow(width, conf, mode) {
    var tbody = document.querySelector('#records-table tbody');
    if (!tbody) return;
    var now = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    var tr = document.createElement('tr');
    tr.innerHTML = '<td>' + (++recordId) + '</td><td>' + now + '</td><td>' + mode + '</td><td style="color:var(--green);">' + width.toFixed(2) + ' mm</td><td>' + (conf * 100).toFixed(1) + '%</td>';
    tbody.prepend(tr);
    while (tbody.children.length > 100) tbody.lastChild.remove();
}

// ===== STATS =====
function updateStats(width) {
    statsData.count++;
    statsData.sum += width;
    if (width > statsData.max) statsData.max = width;
    if (width < statsData.min) statsData.min = width;
    document.getElementById('stat-total').textContent = statsData.count;
    document.getElementById('stat-avg').textContent = (statsData.sum / statsData.count).toFixed(2);
    document.getElementById('stat-max').textContent = statsData.max.toFixed(2);
    document.getElementById('stat-min').textContent = statsData.min.toFixed(2);
}

// ===== TOAST =====
function toast(msg, type) {
    var container = document.getElementById('toast-container');
    if (!container) return;
    var t = document.createElement('div');
    t.className = 'toast ' + (type || '');
    t.textContent = msg;
    container.appendChild(t);
    setTimeout(function() { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; }, 2500);
    setTimeout(function() { t.remove(); }, 3000);
}

bindWidthHover();

// ===== LIGHTBOX ZOOM (dynamic overlay) =====
window.zoomImage = function(img) {
  if (!img || !img.src) return;
  function closeOverlay() {
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    document.body.style.overflow = '';
  }
  var overlay = document.createElement('div');
  overlay.id = '__zoom_overlay__';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:999999;background:rgba(0,0,0,0.95);cursor:zoom-out;display:flex;align-items:center;justify-content:center;touch-action:none;-webkit-user-select:none;user-select:none';
  var lbImg = document.createElement('img');
  lbImg.src = img.src;
  lbImg.style.cssText = 'width:95vw;height:95vh;object-fit:contain;cursor:default;pointer-events:auto';
  var closeBtn = document.createElement('div');
  closeBtn.textContent = '✕';
  closeBtn.style.cssText = 'position:absolute;top:16px;right:24px;color:#65ff9f;font-size:36px;cursor:pointer;z-index:1;font-family:sans-serif;line-height:1;opacity:0.7';
  closeBtn.onmouseenter = function() { closeBtn.style.opacity = '1'; };
  closeBtn.onmouseleave = function() { closeBtn.style.opacity = '0.7'; };
  closeBtn.addEventListener('click', function(e) { e.stopPropagation(); closeOverlay(); });
  overlay.appendChild(lbImg);
  overlay.appendChild(closeBtn);
  overlay.addEventListener('click', function(e) { if (e.target === overlay) closeOverlay(); });
  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';
};
window.closeZoom = function() {
  var ov = document.getElementById('__zoom_overlay__');
  if (ov) { ov.parentNode.removeChild(ov); document.body.style.overflow = ''; }
};
document.addEventListener('keydown', function(e) { if (e.key === 'Escape') window.closeZoom(); });

// Use event delegation on the camera panel
(function() {
  var panel = document.getElementById('cam-left-panel');
  if (!panel) return;
  panel.addEventListener('click', function(e) {
    var img = document.getElementById('cam-left-img');
    if (img && img.src && img.src.indexOf('data:') === 0) {
      window.zoomImage(img);
    }
  });
})();
