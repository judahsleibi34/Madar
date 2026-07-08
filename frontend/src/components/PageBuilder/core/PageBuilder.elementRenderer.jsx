import PageBuilderCarousel from "../ui/PageBuilderCarousel";
import CountUpText from "../ui/CountUpText";
import ReservationBlock from "../blocks/ReservationBlock";
import { resolveMediaUrl } from "../../../utils/media";
import {
  getListItems,
  getRichTextRanges,
  renderRichText,
} from "./PageBuilder.text";
import {
  getMetricItems,
} from "./PageBuilder.layout";
import {
  getComponentPositionClass,
  getCarouselWidthValue,
  getCarouselVariant,
} from "./PageBuilder.elementLayout";

export const createElementRenderer = ({
  carouselElementTypes,
  selected,
  preview,
  getFreeElementStyle,
  getElementStyle,
  startDrag,
  findElementLocation,
  setInsertTarget,
  setSelected,
  captureCanvasTextSelection,
  updateElementInlineText,
  runElementAction,
  renderConnectedForm,
  getReservationBlockValue,
}) => {
  const getEditableTextProps = (element, field = "content", itemIndex = null) => {
    if (preview) return {};

    return {
      contentEditable: true,
      suppressContentEditableWarning: true,
      role: "textbox",
      tabIndex: 0,
      onKeyDown: (event) => {
        event.stopPropagation();
      },
      onBlur: (event) => {
        const nextText = event.currentTarget.textContent || "";

        if (field === "listTitle") {
          if (nextText === (element.listTitle || "")) return;

          updateElementInlineText?.(element.id, {
            listTitle: nextText,
            richTextColors: (element.richTextColors || []).filter((range) => range.field !== "listTitle"),
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
          });
          return;
        }

        if (nextText === String(element.content || "")) return;

        updateElementInlineText?.(element.id, {
          content: nextText,
          richTextColors: (element.richTextColors || []).filter((range) => range.field !== "content"),
        });
      },
    };
  };

  const renderElement = (element, isFree = false) => {
    const isSelected = selected.type === "element" && selected.id === element.id;

    const commonProps = {
      className: `builder-element builder-element-${element.type} ${isSelected ? "is-selected" : ""}`,
      style: isFree ? getFreeElementStyle(element) : getElementStyle(element),
      onMouseDown: (event) => startDrag(event, element),
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

    if (element.type === "heading") {
      return <h1 key={element.id} {...commonProps} {...getEditableTextProps(element)} onMouseUp={(event) => captureCanvasTextSelection(event, "content", null, element.id)}>{renderRichText(element.content, getRichTextRanges(element, "content"))}</h1>;
    }

    if (element.type === "text") {
      return <p key={element.id} {...commonProps} {...getEditableTextProps(element)} onMouseUp={(event) => captureCanvasTextSelection(event, "content", null, element.id)}>{renderRichText(element.content, getRichTextRanges(element, "content"))}</p>;
    }

    if (element.type === "button") {
      return (
        <button
          key={element.id}
          type="button"
          {...commonProps}
          onClick={(event) => {
            commonProps.onClick(event);
            if (preview) runElementAction(element);
          }}
          {...getEditableTextProps(element)}
        >
          {renderRichText(element.content, getRichTextRanges(element, "content"))}
        </button>
      );
    }

    if (element.type === "image") {
      const imageSrc = resolveMediaUrl(element.content);
      return imageSrc ? (
        <img key={element.id} {...commonProps} src={imageSrc} alt={element.name} />
      ) : (
        <div key={element.id} {...commonProps}>Image URL unavailable</div>
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
              autoScroll={Boolean(element.autoScroll)}
              autoScrollMs={element.autoScrollMs}
              content={element.content}
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
          {element.listTitle && <h3 className="builder-list-title" {...getEditableTextProps(element, "listTitle")} onMouseUp={(event) => captureCanvasTextSelection(event, "listTitle", null, element.id)}>{renderRichText(element.listTitle, getRichTextRanges(element, "listTitle"))}</h3>}
          <ul>
            {getListItems(element).map((item, index) => <li key={`${item}_${index}`} style={{ "--list-index": index }} {...getEditableTextProps(element, "listItem", index)} onMouseUp={(event) => captureCanvasTextSelection(event, "listItem", index, element.id)}>{renderRichText(item, getRichTextRanges(element, "listItem", index))}</li>)}
          </ul>
        </div>
      );
    }

    if (element.type === "divider") {
      return <hr key={element.id} {...commonProps} />;
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
              <strong className="metric-value"><CountUpText value={metric.value} /></strong>
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
            submitLabel={reservation.submitLabel}
            disabled={!preview}
          />
        </div>
      );
    }

    return <div key={element.id} {...commonProps}>{element.content}</div>;
  };

  return renderElement;
};
