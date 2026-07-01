import { useEffect, useRef } from "react";
import * as THREE from "three";
import "./OrbitVisual.css";

const TOKENS = {
  madar:    { colors: ["#e8c9a0", "#c08050", "#8b4020", "#4a1a08"], emissive: "#2a0800" },
  records:  { colors: ["#d4b896", "#b07848", "#7a4020", "#3a1400"], emissive: "#1a0600" },
  users:    { colors: ["#c8d4e8", "#8098c0", "#3a5888", "#1b2a4a"], emissive: "#060e20" },
  workflows:{ colors: ["#e8c0a0", "#c07848", "#8b3018", "#4a1000"], emissive: "#1e0600" },
};

const ORBIT_DEFS = [
  {
    key: "one",
    r: 7.5, tiltX: 0.22, tiltZ: 0.14,
    ringColor: 0xb07848,
    speed: 0.52, labelKey: "one", size: 1.0,
    startAngle: 0,
    ...TOKENS.records,
  },
  {
    key: "two",
    r: 11.5, tiltX: -0.18, tiltZ: -0.3,
    ringColor: 0x4a6888,
    speed: 0.33, labelKey: "two", size: 0.85,
    startAngle: (Math.PI * 2) / 3,
    ...TOKENS.users,
  },
  {
    key: "three",
    r: 15.8, tiltX: 0.28, tiltZ: 0.44,
    ringColor: 0x8b3818,
    speed: 0.20, labelKey: "three", size: 1.18,
    startAngle: (Math.PI * 4) / 3,
    ...TOKENS.workflows,
  },
];

const LABEL_MAP = {
  en: { core: "Madar", one: "Records", two: "Users", three: "Workflows" },
  ar: { core: "مدار", one: "السجلات", two: "المستخدمون", three: "سير العمل" },
};

function getCameraSettings(width) {
  if (width < 400)  return { fov: 72, y: 20, z: 38, drift: 1.0 };
  if (width < 640)  return { fov: 65, y: 20, z: 36, drift: 1.2 };
  if (width < 900)  return { fov: 55, y: 20, z: 34, drift: 1.8 };
  return              { fov: 42, y: 22, z: 42, drift: 2.4 };
}

function buildTexture(colors) {
  const res = 1024;
  const cv  = document.createElement("canvas");
  cv.width  = cv.height = res;
  const ctx = cv.getContext("2d");
  const grd = ctx.createLinearGradient(0, 0, 0, res);

  colors.forEach((c, i) => grd.addColorStop(i / (colors.length - 1), c));

  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, res, res);

  for (let i = 0; i < 28; i++) {
    const y = Math.random() * res;
    const h = 2 + Math.random() * 20;
    const a = 0.04 + Math.random() * 0.16;

    ctx.fillStyle = Math.random() > 0.5
      ? `rgba(255,220,160,${a})`
      : `rgba(30,10,5,${a})`;

    ctx.fillRect(0, y, res, h);
  }

  for (let s = 0; s < 3; s++) {
    const cx = Math.random() * res;
    const cy = Math.random() * res;
    const r = 20 + Math.random() * 50;
    const rg = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);

    rg.addColorStop(0, `rgba(255,190,100,0.16)`);
    rg.addColorStop(0.5, `rgba(160,60,10,0.08)`);
    rg.addColorStop(1, "rgba(0,0,0,0)");

    ctx.fillStyle = rg;
    ctx.beginPath();
    ctx.ellipse(cx, cy, r, r * 0.38, Math.random() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }

  for (let i = 0; i < 5000; i++) {
    ctx.fillStyle = `rgba(255,255,255,${Math.random() * 0.025})`;
    ctx.fillRect(Math.random() * res, Math.random() * res, 1, 1);
  }

  return new THREE.CanvasTexture(cv);
}

function buildNormalMap() {
  const res = 512;
  const cv  = document.createElement("canvas");
  cv.width  = cv.height = res;
  const ctx = cv.getContext("2d");

  ctx.fillStyle = "#8080ff";
  ctx.fillRect(0, 0, res, res);

  for (let i = 0; i < 22; i++) {
    const y = Math.random() * res;
    const h = 3 + Math.random() * 16;
    const d = (Math.random() - 0.5) * 28;

    ctx.fillStyle = `rgba(${128 + d},${128 + d * 0.4},255,0.55)`;
    ctx.fillRect(0, y, res, h);
  }

  return new THREE.CanvasTexture(cv);
}

function makePlanetGroup(radius, colors, emissive, hasRings = false) {
  const group = new THREE.Group();

  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(radius, 80, 80),
    new THREE.MeshStandardMaterial({
      map: buildTexture(colors),
      normalMap: buildNormalMap(),
      normalScale: new THREE.Vector2(1.1, 1.1),
      roughness: 0.42,
      metalness: 0.0,
      emissive: new THREE.Color(emissive),
      emissiveIntensity: 0.20,
    })
  );

  sphere.castShadow = sphere.receiveShadow = true;
  group.add(sphere);

  group.add(new THREE.Mesh(
    new THREE.SphereGeometry(radius * 1.09, 32, 32),
    new THREE.MeshPhongMaterial({
      color: new THREE.Color(colors[1]),
      transparent: true,
      opacity: 0.09,
      side: THREE.BackSide,
    })
  ));

  group.add(new THREE.Mesh(
    new THREE.SphereGeometry(radius * 1.002, 32, 32),
    new THREE.MeshPhongMaterial({
      color: 0x000000,
      specular: 0xffffff,
      shininess: 200,
      transparent: true,
      opacity: 0.16,
    })
  ));

  if (hasRings) {
    [
      { inner: 1.28, outer: 1.72, color: 0xc8a070, opacity: 0.55 },
      { inner: 1.76, outer: 2.22, color: 0x8b4820, opacity: 0.28 },
    ].forEach(({ inner, outer, color, opacity }) => {
      const r = new THREE.Mesh(
        new THREE.RingGeometry(radius * inner, radius * outer, 96),
        new THREE.MeshBasicMaterial({
          color,
          side: THREE.DoubleSide,
          transparent: true,
          opacity,
        })
      );

      r.rotation.x = Math.PI / 2.3;
      group.add(r);
    });
  }

  return { group, sphere };
}

function makeOrbitLine(r, tiltX, tiltZ, color) {
  const pts = new THREE.EllipseCurve(0, 0, r, r, 0, Math.PI * 2)
    .getPoints(180)
    .map((p) => new THREE.Vector3(p.x, 0, p.y));

  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: 0.28,
    })
  );

  line.rotation.x = tiltX;
  line.rotation.z = tiltZ;

  return line;
}

const _euler = new THREE.Euler();
const _quat  = new THREE.Quaternion();
const _local = new THREE.Vector3();

function orbitPosition(angle, r, tiltX, tiltZ, out) {
  _local.set(Math.cos(angle) * r, 0, Math.sin(angle) * r);
  _euler.set(tiltX, 0, tiltZ, "XYZ");
  _quat.setFromEuler(_euler);
  out.copy(_local).applyQuaternion(_quat);
}

function createLabel(text, extraClass = "") {
  const el = document.createElement("div");
  el.textContent = text;
  el.className = "orbit-label" + (extraClass ? " " + extraClass : "");
  return el;
}


export default function OrbitVisual({ lang = "en" }) {
  const containerRef = useRef(null);
  const labelsRef    = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    const labelsEl  = labelsRef.current;

    if (!container || !labelsEl) return;

    const t = LABEL_MAP[lang] || LABEL_MAP.en;

    let W = container.clientWidth;
    let H = container.clientHeight;

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
    });

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.setClearColor(0x000000, 0);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.35;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.className = "orbit-visual-canvas";

    container.prepend(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = scene.fog = null;

    let camSettings = getCameraSettings(W);

    const camera = new THREE.PerspectiveCamera(
      camSettings.fov,
      W / H,
      0.1,
      500
    );

    camera.position.set(0, camSettings.y, camSettings.z);
    camera.lookAt(0, 0, 0);

    const sun = new THREE.PointLight(0xffe8c0, 5.0, 200);
    sun.position.set(12, 16, 10);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -0.001;
    scene.add(sun);

    const fill = new THREE.DirectionalLight(0xffd4a0, 1.1);
    fill.position.set(-8, 4, 14);
    scene.add(fill);

    const rim = new THREE.DirectionalLight(0x1a2744, 1.2);
    rim.position.set(-6, -4, -14);
    scene.add(rim);

    scene.add(new THREE.AmbientLight(0x111b31, 1.0));

    const sv = [];

    for (let i = 0; i < 2200; i++) {
      sv.push(
        (Math.random() - 0.5) * 500,
        (Math.random() - 0.5) * 500,
        (Math.random() - 0.5) * 500
      );
    }

    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.Float32BufferAttribute(sv, 3));

    const stars = new THREE.Points(
      starGeo,
      new THREE.PointsMaterial({
        color: 0xf5f2ee,
        size: 0.20,
        transparent: true,
        opacity: 0.80,
      })
    );

    scene.add(stars);

    const { group: madarGroup, sphere: madarSphere } = makePlanetGroup(
      3.2,
      TOKENS.madar.colors,
      TOKENS.madar.emissive,
      true
    );

    scene.add(madarGroup);

    const _pos = new THREE.Vector3();

    const planets = ORBIT_DEFS.map((def) => {
      scene.add(makeOrbitLine(def.r, def.tiltX, def.tiltZ, def.ringColor));

      const { group, sphere } = makePlanetGroup(
        def.size,
        def.colors,
        def.emissive
      );

      scene.add(group);

      const lbl = createLabel(t[def.labelKey]);
      labelsEl.appendChild(lbl);

      return {
        ...def,
        group,
        sphere,
        angle: def.startAngle,
        lbl,
      };
    });

    const _ndc = new THREE.Vector3();

    function toScreen(worldPos) {
      _ndc.copy(worldPos).project(camera);

      return {
        x: (_ndc.x * 0.5 + 0.5) * W,
        y: (_ndc.y * -0.5 + 0.5) * H,
        behind: _ndc.z > 1,
      };
    }

    function planetScreenRadius(worldPos, worldRadius) {
      const dist = worldPos.distanceTo(camera.position);
      const fovRad = THREE.MathUtils.degToRad(camera.fov);

      return (worldRadius / (dist * Math.tan(fovRad / 2))) * (H / 2);
    }

    let tick = 0;
    let rafId;

    function animate() {
      rafId = requestAnimationFrame(animate);
      tick += 0.008;

      camera.position.x = Math.sin(tick * 0.28) * camSettings.drift;
      camera.position.y = camSettings.y + Math.sin(tick * 0.20) * 1.3;
      camera.lookAt(0, 0, 0);

      madarSphere.rotation.y += 0.003;
      stars.rotation.y += 0.00008;

      const planetScreenData = [];

      planets.forEach((p) => {
        p.angle += p.speed * 0.009;

        orbitPosition(p.angle, p.r, p.tiltX, p.tiltZ, _pos);

        p.group.position.copy(_pos);
        p.sphere.rotation.y += 0.010;
        p.sphere.rotation.x += 0.002;

        const dist = _pos.distanceTo(camera.position);

        p.group.scale.setScalar(
          Math.max(0.65, Math.min(1.35, 1 + (28 - dist) * 0.007))
        );

        const s = toScreen(p.group.position);
        const screenR = planetScreenRadius(p.group.position, p.size * 1.35);

        planetScreenData.push({
          p,
          s,
          screenR,
        });
      });

      const getLblSize = (el) => {
        const r = el.getBoundingClientRect();

        return {
          w: r.width || 70,
          h: r.height || 22,
        };
      };

      const allPlanets = planetScreenData.map((d) => ({
        s: d.s,
        screenR: d.screenR,
        lbl: d.p.lbl,
      }));

      const boxes = allPlanets.map(({ s, screenR, lbl }) => {
        const { w, h } = getLblSize(lbl);

        return {
          lbl,
          w,
          h,
          x: s.x,
          y: s.y - screenR - h / 2 - 5,
          planetX: s.x,
          planetY: s.y,
          planetR: screenR,
        };
      });

      boxes.forEach(({ lbl, x, y }) => {
        lbl.style.opacity = "1";
        lbl.style.left = x + "px";
        lbl.style.top = y + "px";
      });

      planetScreenData.forEach(({ p, s }) => {
        if (s.behind) p.lbl.style.opacity = "0";
      });

      renderer.render(scene, camera);
    }

    animate();

    const observer = new MutationObserver(() => {
      scene.background = scene.fog = null;
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "class"],
    });

    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["class"],
    });

    const onResize = () => {
      W = container.clientWidth;
      H = container.clientHeight;

      renderer.setSize(W, H);

      camera.aspect = W / H;
      camSettings = getCameraSettings(W);
      camera.fov = camSettings.fov;
      camera.position.set(0, camSettings.y, camSettings.z);
      camera.updateProjectionMatrix();
    };

    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
      observer.disconnect();
      renderer.dispose();

      planets.forEach((p) => p.lbl.remove());
      renderer.domElement.remove();
    };
  }, [lang]);

  return (
    <div
      ref={containerRef}
      className="orbit-visual-container"
      aria-label="Madar planetary orbit visual"
    >
      <div ref={labelsRef} className="orbit-visual-labels" />
    </div>
  );
}
