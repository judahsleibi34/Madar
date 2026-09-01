import PageBuilderCarousel from "../ui/PageBuilderCarousel";
import AutoFitDirectText from "./PageBuilder.autoFitText";
import LazyBuilderVideo from "./LazyBuilderVideo";
import DocumentViewerElement from "./DocumentViewerElement";
import CountUpText from "../ui/CountUpText";
import { BuilderIcon } from "../ui/PageBuilderIconPicker";
import ReservationBlock from "../blocks/ReservationBlock";
import PhotoProofingBlock from "../blocks/PhotoProofingBlock";
import { getResponsiveMediaProps, resolveDocumentUrl, resolveMediaUrl } from "../../../utils/media";
import {
  collapseAccidentalTextDuplication,
  getEditableTextBlockFormats,
  getEditableTextWithLineBreaks,
  getListItems,
  getRichTextRanges,
  renderRichText,
  renderRichTextBlocks,
} from "./PageBuilder.text";
import {
  getMetricItems,
} from "./PageBuilder.layout";
import {
  getComponentPositionClass,
  getCarouselWidthValue,
  getCarouselVariant,
} from "./PageBuilder.elementLayout";
import { getElementHeadingTag } from "./PageBuilder.heading";
import { getButtonColorPresentation } from "./PageBuilder.buttonColors";

export const createElementRenderer = ({
  carouselElementTypes,
  selected,
  preview,
  renderMode = preview ? "preview" : "editing",
  getFreeElementStyle,
  getElementStyle,
  startDrag,
  findElementLocation,
  setInsertTarget,
  setSelected,
  captureCanvasTextSelection,
  shouldIgnoreInlineTextBlur,
  updateElementInlineText,
  runElementAction,
  renderConnectedForm,
  getReservationBlockValue,
  renderElementOverride,
}) => {
  const getTextRanges = (element, field, itemIndex = null) =>
    getRichTextRanges(element, field, itemIndex);

  const getEditableTextProps = (element, field = "content", itemIndex = null) => {
    if (preview) return {};

    return {
      contentEditable: true,
      suppressContentEditableWarning: true,
      role: "textbox",
      tabIndex: 0,
      onKeyDown: (event) => {
        event.stopPropagation();
        if (event.key === "Enter" && field === "content" && ["heading", "text"].includes(element.type)) {
          event.preventDefault();
          const selection = window.getSelection();
          if (selection?.rangeCount) {
            const range = selection.getRangeAt(0);
            if (event.currentTarget.contains(range.startContainer)) {
              range.deleteContents();
              const currentBlock = (range.startContainer.nodeType === 1
                ? range.startContainer
                : range.startContainer.parentElement)?.closest?.("[data-builder-text-block]");
              if (!currentBlock || !event.currentTarget.contains(currentBlock)) return;

              const trailingRange = document.createRange();
              trailingRange.setStart(range.startContainer, range.startOffset);
              trailingRange.setEnd(currentBlock, currentBlock.childNodes.length);
              const trailingContent = trailingRange.extractContents();
              const nextBlock = document.createElement("p");
              nextBlock.dataset.builderTextBlock = "text";
              nextBlock.append(trailingContent);
              if (!nextBlock.textContent && !nextBlock.querySelector("br")) nextBlock.append(document.createElement("br"));
              currentBlock.after(nextBlock);
              if (!currentBlock.textContent && !currentBlock.querySelector("br")) currentBlock.append(document.createElement("br"));

              range.selectNodeContents(nextBlock);
              range.collapse(true);
              selection.removeAllRanges();
              selection.addRange(range);
              event.currentTarget.dataset.builderTextEdited = "true";
              captureCanvasTextSelection?.(event, "content", null, element.id, { silent: true });
              const toolbarSelect = document.querySelector(
                '.builder-inline-text-toolbar select[aria-label="Text style"]'
              );
              if (toolbarSelect) toolbarSelect.value = "text";
            }
          }
        }
      },
      onKeyUp: (event) => {
        if (field === "content" && ["heading", "text"].includes(element.type)) {
          captureCanvasTextSelection?.(event, field, itemIndex, element.id, { silent: true });
        }
      },
      onFocus: (event) => {
        event.currentTarget.dataset.builderTextEdited = "false";
        if (field !== "content") return;

        const currentText = String(element.content || "");
        const repairedText = collapseAccidentalTextDuplication(currentText);
        if (repairedText === currentText) return;

        updateElementInlineText?.(element.id, {
          content: repairedText,
          richTextColors: (element.richTextColors || []).filter(
            (range) => range.field !== "content"
          ),
          richTextSizes: (element.richTextSizes || []).filter(
            (range) => range.field !== "content"
          ),
          richTextStyles: (element.richTextStyles || []).filter(
            (range) => range.field !== "content"
          ),
        });
      },
      onInput: (event) => {
        event.currentTarget.dataset.builderTextEdited = "true";
      },
      onBlur: (event) => {
        if (field === "content" && ["heading", "text"].includes(element.type)) {
          captureCanvasTextSelection?.(event, field, itemIndex, element.id);
        }
        const wasEdited = event.currentTarget.dataset.builderTextEdited === "true";
        if (shouldIgnoreInlineTextBlur?.(event) && !wasEdited) return;
        if (!wasEdited) return;
        event.currentTarget.dataset.builderTextEdited = "false";

        const rawText = getEditableTextWithLineBreaks(event.currentTarget);
        const nextText = field === "content"
          ? collapseAccidentalTextDuplication(rawText)
          : rawText;

        if (field === "listTitle") {
          if (nextText === (element.listTitle || "")) return;

          updateElementInlineText?.(element.id, {
            listTitle: nextText,
            richTextColors: (element.richTextColors || []).filter((range) => range.field !== "listTitle"),
            richTextSizes: (element.richTextSizes || []).filter((range) => range.field !== "listTitle"),
            richTextStyles: (element.richTextStyles || []).filter((range) => range.field !== "listTitle"),
          });
          return;
        }

        if (field === "listItem") {
          const listItems = getListItems(element);
          if (nextText === (listItems[itemIndex] || "")) return;

          const nextItems = listItems.map((item, index) => (index === itemIndex ? nextText : item));
          updateElementInlineText?.(element.id, {
            listItems: nextItems,
            content: nextItems.join("\n"),
            richTextColors: (element.richTextColors || []).filter(
              (range) => !(range.field === "listItem" && range.itemIndex === itemIndex)
            ),
            richTextSizes: (element.richTextSizes || []).filter(
              (range) => !(range.field === "listItem" && range.itemIndex === itemIndex)
            ),
            richTextStyles: (element.richTextStyles || []).filter(
              (range) => !(range.field === "listItem" && range.itemIndex === itemIndex)
            ),
          });
          return;
        }

        if (nextText === String(element.content || "")) return;

        updateElementInlineText?.(element.id, {
          content: nextText,
          ...(["heading", "text"].includes(element.type)
            ? { textBlockFormats: getEditableTextBlockFormats(event.currentTarget, element.type === "heading" ? getElementHeadingTag(element) : "text") }
            : {}),
          richTextColors: (element.richTextColors || []).filter((range) => range.field !== "content"),
          richTextSizes: (element.richTextSizes || []).filter((range) => range.field !== "content"),
          richTextStyles: (element.richTextStyles || []).filter((range) => range.field !== "content"),
        });
      },
    };
  };

  const renderElement = (element, isFree = false) => {
    const isSelected = selected.type === "element" && selected.id === element.id;

    const commonProps = {
      className: `builder-element builder-element-${element.type} ${isSelected ? "is-selected" : ""}`,
      style: isFree ? getFreeElementStyle(element) : getElementStyle(element),
      onPointerDown: (event) => startDrag(event, element),
      onClick: (event) => {
        event.stopPropagation();
        if (!preview) {
          const location = findElementLocation(element.id);
          if (location?.isFree === false) {
            setInsertTarget({
              sectionId: location.sectionId,
              mode: "auto",
              columnId: location.columnId,
              afterElementId: element.id,
            });
          } else if (location?.isFree) {
            setInsertTarget({
              sectionId: location.sectionId,
              mode: "direct",
              afterElementId: element.id,
            });
          }
          setSelected({ type: "element", id: element.id });
        }
      },
    };

    const overridden = renderElementOverride?.(element, {
      commonProps,
      getEditableTextProps,
      getTextRanges,
      renderMode,
    });
    if (overridden !== undefined) return overridden;

    if (element.type === "heading") {
      return <AutoFitDirectText preserveFontSize as="div" fitKey={`${element.content}:${JSON.stringify(element.textBlockFormats || [])}:${element.styles?.fontSize || ""}:${element.styles?.fontFamily || ""}:${element.styles?.lineHeight || ""}:${JSON.stringify(element.richTextSizes || [])}:${JSON.stringify(element.richTextStyles || [])}`} key={`${element.id}:${element.content}:${JSON.stringify(element.textBlockFormats || [])}`} {...commonProps} {...getEditableTextProps(element)} onMouseUp={(event) => captureCanvasTextSelection(event, "content", null, element.id)}>{renderRichTextBlocks(element, getTextRanges(element, "content"))}</AutoFitDirectText>;
    }

    if (element.type === "text") {
      return <AutoFitDirectText preserveFontSize as="div" fitKey={`${element.content}:${JSON.stringify(element.textBlockFormats || [])}:${element.styles?.fontSize || ""}:${element.styles?.fontFamily || ""}:${element.styles?.lineHeight || ""}:${JSON.stringify(element.richTextSizes || [])}:${JSON.stringify(element.richTextStyles || [])}`} key={`${element.id}:${element.content}:${JSON.stringify(element.textBlockFormats || [])}`} {...commonProps} {...getEditableTextProps(element)} onMouseUp={(event) => captureCanvasTextSelection(event, "content", null, element.id)}>{renderRichTextBlocks(element, getTextRanges(element, "content"))}</AutoFitDirectText>;
    }

    if (element.type === "button") {
      const presentation = getButtonColorPresentation(element);
      const buttonProps = {
        ...commonProps,
        className: `${commonProps.className} ${presentation.className}`.trim(),
        style: { ...commonProps.style, ...presentation.style },
        ...(preview && element.disabled ? { disabled: true } : {}),
      };
      return (
        <AutoFitDirectText
          as="button"
          fitKey={`${element.content}:${element.styles?.fontSize || ""}:${element.styles?.fontFamily || ""}:${JSON.stringify(element.richTextSizes || [])}:${JSON.stringify(element.richTextStyles || [])}`}
          key={element.id}
          type="button"
          {...buttonProps}
          onClick={(event) => {
            commonProps.onClick(event);
            if (preview) runElementAction(element);
          }}
          {...getEditableTextProps(element)}
        >
          {renderRichText(element.content, getTextRanges(element, "content"))}
        </AutoFitDirectText>
      );
    }

    if (element.type === "imageButton") {
      const imageProps = getResponsiveMediaProps(element.content, {
        sizes: element.imageButtonVariant === "editorialCard"
          ? "(max-width: 720px) 100vw, 280px"
          : "100vw",
      });
      const imageSrc = imageProps.src;
      const isEditorialCard = element.imageButtonVariant === "editorialCard";
      const savedCardMediaWidth = Number(element.imageCardMediaWidth);
      const cardMediaWidth = savedCardMediaWidth > 65
        ? Math.max(140, Math.min(280, savedCardMediaWidth))
        : 200;
      return (
        <button
          key={element.id}
          type="button"
          {...commonProps}
          className={`${commonProps.className} ${isEditorialCard ? "is-editorial-card" : ""}`.trim()}
          style={{
            ...commonProps.style,
            ...(isEditorialCard
              ? { "--image-card-media-width": `${cardMediaWidth}px` }
              : {}),
          }}
          aria-label={isEditorialCard ? (element.cardTitle || element.name || "Image card button") : (element.name || "Image button")}
          onClick={(event) => {
            commonProps.onClick(event);
            if (preview) runElementAction(element);
          }}
        >
          {isEditorialCard ? (
            <>
              <span className="image-button-card-media">
                {imageSrc ? (
                  <img {...imageProps} alt="" loading="lazy" decoding="async" />
                ) : (
                  <span className="image-button-card-placeholder">Upload image</span>
                )}
              </span>
              <span className="image-button-card-copy">
                {element.cardIcon !== "none" && (
                  <span className="image-button-card-icon" aria-hidden="true">
                    <BuilderIcon name={element.cardIcon || "Sparkles"} />
                  </span>
                )}
                <span className="image-button-card-title">{element.cardTitle || "Celebrations"}</span>
                <span className="image-button-card-description">{element.cardDescription || "Add a short description for this destination."}</span>
                <span className="image-button-card-action">{element.cardActionLabel || "Explore"}<span aria-hidden="true">→</span></span>
              </span>
            </>
          ) : imageSrc ? (
            <img {...imageProps} alt="" loading="lazy" decoding="async" />
          ) : (
            <span>Upload button image</span>
          )}
        </button>
      );
    }

    if (element.type === "image") {
      const imageProps = getResponsiveMediaProps(element.content);
      return imageProps.src ? (
        <img
          key={element.id}
          {...commonProps}
          {...imageProps}
          alt={element.name}
          loading="lazy"
          decoding="async"
        />
      ) : (
        <div key={element.id} {...commonProps}>Image URL unavailable</div>
      );
    }

    if (element.type === "video") {
      const videoSrc = resolveMediaUrl(element.content);
      return videoSrc ? (
        <LazyBuilderVideo
          key={`${element.id}:${element.video?.controls !== false}:${Boolean(element.video?.muted)}:${Boolean(element.video?.loop)}`}
          {...commonProps}
          src={videoSrc}
          controls={element.video?.controls !== false}
          muted={Boolean(element.video?.muted)}
          loop={Boolean(element.video?.loop)}
          aria-label={element.name || "Video"}
        />
      ) : (
        <div key={element.id} {...commonProps}>Upload an MP4 or WebM video</div>
      );
    }

    if (element.type === "document") {
      return (
        <DocumentViewerElement
          key={element.id}
          {...commonProps}
          src={resolveDocumentUrl(element.content)}
          fileName={element.assetFileName}
          mimeType={element.documentMimeType}
          title={element.document?.title}
          description={element.document?.description}
          interactive
        />
      );
    }

    if (element.type === "photoProofing") {
      return (
        <div key={element.id} {...commonProps}>
          <PhotoProofingBlock content={element.content} settings={element.proofing} disabled={!preview} />
        </div>
      );
    }

    if (carouselElementTypes.has(element.type)) {
      const carouselWidth = getCarouselWidthValue(element);
      const carouselFrameStyle = {
        ...commonProps.style,
        width: "100%",
        maxWidth: "100%",
        alignSelf: "stretch",
        marginLeft: undefined,
        marginRight: undefined,
        "--builder-element-width": "100%",
        "--builder-element-align": "stretch",
      };

      return (
        <div
          key={element.id}
          {...commonProps}
          className={`${commonProps.className} carousel-position-frame ${getComponentPositionClass(element.styles.alignSelf)}`}
          style={carouselFrameStyle}
        >
          <div
            className="carousel-position-inner"
            style={{ width: carouselWidth, maxWidth: carouselWidth }}
          >
            <PageBuilderCarousel
              autoScroll={renderMode !== "editing" && Boolean(element.autoScroll)}
              autoScrollMs={element.autoScrollMs}
              content={element.content}
              logoSliderSubtitle={element.logoSliderSubtitle}
              logoSliderTitle={element.logoSliderTitle}
              name={element.name}
              variant={getCarouselVariant(element)}
            />
          </div>
        </div>
      );
    }

    if (element.type === "list") {
      return (
        <div key={element.id} {...commonProps} className={`${commonProps.className} list-style-${element.listStyle || "disc"}`} style={{ ...commonProps.style, "--list-count": Math.max(1, getListItems(element).length) }}>
          {element.listTitle && <h3 className="builder-list-title" {...getEditableTextProps(element, "listTitle")} onMouseUp={(event) => captureCanvasTextSelection(event, "listTitle", null, element.id)}>{renderRichText(element.listTitle, getTextRanges(element, "listTitle"))}</h3>}
          <ul>
            {getListItems(element).map((item, index) => <li key={`${item}_${index}`} style={{ "--list-index": index }} {...getEditableTextProps(element, "listItem", index)} onMouseUp={(event) => captureCanvasTextSelection(event, "listItem", index, element.id)}>{renderRichText(item, getTextRanges(element, "listItem", index))}</li>)}
          </ul>
        </div>
      );
    }

    if (element.type === "divider" || element.type === "thinDivider") {
      const dividerStyle = element.type === 'thinDivider'
        ? {
            ...commonProps.style,
            '--divider-color': element.styles?.color || 'var(--theme-border-strong)',
          }
        : commonProps.style;

      return (
        <div
          key={element.id}
          {...commonProps}
          role='separator'
          aria-orientation='horizontal'
          style={dividerStyle}
        />
      );
    }

    if (element.type === "embed") {
      return (
        <div key={element.id} {...commonProps}>
          <strong>Embed</strong>
          <a href={element.content} target="_blank" rel="noreferrer">{element.content}</a>
        </div>
      );
    }

    if (element.type === "metric") {
      const metrics = getMetricItems(element);
      const columns = Math.max(2, Math.min(4, Number(element.metricColumns) || 2));
      return (
        <div key={element.id} {...commonProps} className={`${commonProps.className} metric-group`} style={{ ...commonProps.style, "--metric-columns": columns, "--metric-text-color": element.styles?.metricTextColor || "var(--theme-text)", "--metric-symbol-color": element.styles?.metricSymbolColor || "var(--theme-warning)" }}>
          {metrics.map((metric, index) => (
            <div className="metric-group-item" key={`${element.id}_${index}`}>
              <strong className="metric-value"><CountUpText value={metric.value} animateValue={renderMode !== "editing"} /></strong>
              <span className="metric-label">{metric.label}</span>
              {metric.description && <span className="metric-description">{metric.description}</span>}
            </div>
          ))}
        </div>
      );
    }

    if (element.type === "loginBlock" || element.type === "registrationBlock") {
      const isRegistration = element.type === "registrationBlock";
      const auth = element.auth || {};

      return (
        <div key={element.id} {...commonProps}>
          <div className="builder-auth-component">
            <div className="builder-auth-heading">
              <h3>{auth.title || (isRegistration ? "Create account" : "Log in")}</h3>
              <p>{auth.subtitle || (isRegistration ? "Create your account." : "Access your account.")}</p>
            </div>
            {isRegistration && <label>Full name<input type="text" name={`builder-demo-name-${element.id}`} autoComplete="off" placeholder="Your name" disabled={!preview} /></label>}
            <label>Email address<input type="email" name={`builder-demo-email-${element.id}`} autoComplete="off" placeholder="name@example.com" disabled={!preview} /></label>
            <label>Password<input type="password" name={`builder-demo-password-${element.id}`} autoComplete="new-password" placeholder="Enter password" disabled={!preview} /></label>
            {isRegistration && <label>Confirm password<input type="password" name={`builder-demo-confirm-${element.id}`} autoComplete="new-password" placeholder="Confirm password" disabled={!preview} /></label>}
            <button type="button" className="runtime-submit">
              {auth.buttonText || (isRegistration ? "Create account" : "Log in")}
            </button>
            <p className="builder-auth-switch">
              {auth.switchText} <strong>{auth.switchActionText}</strong>
            </p>
          </div>
        </div>
      );
    }

    if (element.type === "formBlock") {
      const formBlockProps = preview
        ? {
            className: commonProps.className,
            style: commonProps.style,
          }
        : commonProps;

      return <div key={element.id} {...formBlockProps}>{renderConnectedForm(element.connectedFormId)}</div>;
    }

    if (element.type === "reservationBlock") {
      const reservation = getReservationBlockValue?.(element) || element.reservation || {};

      return (
        <div key={element.id} {...commonProps}>
          <ReservationBlock
            title={reservation.title}
            description={reservation.description}
            services={reservation.services}
            fields={reservation.fields}
            formItems={reservation.formItems}
            bookingMode={reservation.bookingMode}
            availableDates={reservation.availableDates}
            timeSlots={reservation.timeSlots}
            timeSlotsByDate={reservation.timeSlotsByDate}
            submitLabel={reservation.submitLabel}
            disabled
          />
        </div>
      );
    }

    return <div key={element.id} {...commonProps}>{element.content}</div>;
  };

  return renderElement;
};
