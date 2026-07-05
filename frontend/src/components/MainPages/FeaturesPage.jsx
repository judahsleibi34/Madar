import { useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  Eye,
  GripVertical,
  LayoutTemplate,
  MousePointer2,
  PlayCircle,
  Plus,
} from "lucide-react";
import { Link } from "react-router-dom";
import GradientText from "../Animations/GradientText";
import { getFeaturesContent } from "../../content";
import { CardGridBlock, CTASectionBlock, HeroBlock } from "../../blocks";
import { PUBLIC_ROUTES } from "../../config/routes";

function ProductBuilderDemo({ t }) {
  const demoBlockCatalog = t.builderDemoBlocks;
  const [blocks, setBlocks] = useState(["hero", "services", "form"]);
  const [selectedBlock, setSelectedBlock] = useState("hero");
  const [draggedIndex, setDraggedIndex] = useState(null);

  const selected = useMemo(
    () => demoBlockCatalog.find((block) => block.id === selectedBlock),
    [demoBlockCatalog, selectedBlock],
  );

  const addBlock = (blockId) => {
    setBlocks((current) => [...current, blockId]);
    setSelectedBlock(blockId);
  };

  const moveBlock = (index, direction) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= blocks.length) return;

    setBlocks((current) => {
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(nextIndex, 0, item);
      return next;
    });
  };

  const handleDrop = (dropIndex) => {
    if (draggedIndex === null || draggedIndex === dropIndex) return;

    setBlocks((current) => {
      const next = [...current];
      const [item] = next.splice(draggedIndex, 1);
      next.splice(dropIndex, 0, item);
      return next;
    });
    setDraggedIndex(null);
  };

  return (
    <section className="tour-builder-demo" aria-label={t.builderDemoTitle}>
      <div className="tour-builder-heading">
        <div>
          <span>{t.builderDemoKicker}</span>
          <h2>{t.builderDemoTitle}</h2>
          <p>{t.builderDemoDescription}</p>
        </div>
        <Link className="tour-builder-open-demo" to={PUBLIC_ROUTES.demo}>
          <PlayCircle size={18} />
          {t.demoCta}
        </Link>
      </div>

      <div className="tour-builder-shell">
        <aside className="tour-builder-sidebar" aria-label={t.builderDemoComponentsLabel}>
          <div className="tour-builder-sidebar-title">
            <LayoutTemplate size={18} />
            <span>{t.builderDemoComponentsTitle}</span>
          </div>
          <div className="tour-builder-palette">
            {demoBlockCatalog.map((block) => (
              <button
                className="tour-builder-add"
                key={block.id}
                type="button"
                onClick={() => addBlock(block.id)}
              >
                <Plus size={16} />
                {block.label}
              </button>
            ))}
          </div>
        </aside>

        <div className="tour-builder-canvas" aria-label={t.builderDemoPreviewLabel}>
          <div className="tour-builder-toolbar">
            <div>
              <Eye size={17} />
              <span>{t.builderDemoPreviewTitle}</span>
            </div>
            <span>{blocks.length} {t.builderDemoSectionsLabel}</span>
          </div>

          <div className="tour-builder-preview">
            {blocks.map((blockId, index) => {
              const block = demoBlockCatalog.find((item) => item.id === blockId);
              const instanceId = `${blockId}-${index}`;

              return (
                <article
                  className={`tour-builder-block ${
                    selectedBlock === blockId ? "is-selected" : ""
                  }`}
                  draggable
                  key={instanceId}
                  onClick={() => setSelectedBlock(blockId)}
                  onDragStart={() => setDraggedIndex(index)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => handleDrop(index)}
                >
                  <div className="tour-builder-block-handle" aria-hidden="true">
                    <GripVertical size={18} />
                  </div>
                  <div className="tour-builder-block-content">
                    <span>{block.title}</span>
                    <h3>{block.previewTitle}</h3>
                    <p>{block.previewText}</p>
                  </div>
                  <div className="tour-builder-block-actions">
                    <button
                      aria-label={t.builderDemoMoveUp}
                      disabled={index === 0}
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        moveBlock(index, -1);
                      }}
                    >
                      <ArrowUp size={15} />
                    </button>
                    <button
                      aria-label={t.builderDemoMoveDown}
                      disabled={index === blocks.length - 1}
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        moveBlock(index, 1);
                      }}
                    >
                      <ArrowDown size={15} />
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </div>

        <aside className="tour-builder-inspector" aria-label={t.builderDemoSelectedLabel}>
          <div className="tour-builder-sidebar-title">
            <MousePointer2 size={18} />
            <span>{t.builderDemoSelectedTitle}</span>
          </div>
          <h3>{selected?.title}</h3>
          <p>{t.builderDemoSelectedDescription}</p>
        </aside>
      </div>
    </section>
  );
}

export default function FeaturesPage({ lang = "en" }) {
  const t = getFeaturesContent(lang);

  return (
    <main className="features-page">
      <HeroBlock className="features-hero">
        <h1>
          {lang === "en" ? (
            <>
              {t.titleParts[0]}{" "}
              <GradientText pauseOnHover>{t.titleParts[1]}</GradientText>,{" "}
              {t.titleParts[2]}{" "}
              <GradientText pauseOnHover>{t.titleParts[3]}</GradientText>
            </>
          ) : (
            <GradientText pauseOnHover>{t.title}</GradientText>
          )}
        </h1>
        <p>{t.subtitle}</p>
      </HeroBlock>

      <ProductBuilderDemo t={t} />

      <CTASectionBlock className="features-demo-panel" aria-label={t.demoTitle}>
        <div className="features-demo-copy">
          <div className="features-demo-icon">
            <PlayCircle size={26} />
          </div>
          <div>
            <h2>
              <GradientText pauseOnHover>{t.demoTitle}</GradientText>
            </h2>
            <p>{t.demoDescription}</p>
          </div>
        </div>

        <ul className="features-demo-list">
          {t.demoPoints.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>

        <Link className="features-demo-cta" to={PUBLIC_ROUTES.demo}>
          {t.demoCta}
        </Link>
      </CTASectionBlock>

      <CardGridBlock
        className="features-grid"
        aria-label={t.eyebrow}
        items={t.features}
        renderItem={(feature) => {
          const Icon = feature.icon;

          return (
            <article className="feature-card" key={feature.title}>
              <div className="feature-card-icon">
                <Icon size={22} />
              </div>
              <h2>
                <GradientText pauseOnHover>{feature.title}</GradientText>
              </h2>
              <p>{feature.description}</p>
            </article>
          );
        }}
      />
    </main>
  );
}
