define("SBEFolderGalleryListingSetup", [
  "Abilian",
  "jquery",
  "jquery.dataTables",
  "bootbox",
], (Abilian, $, jqDT, bootbox) => {
  "use strict";
  function setupFolderListing() {
    $.fn.dataTableExt.afnFiltering.push((oSettings, aData, iDataIndex) => {
      const filter_value = $("#filter").val();
      const row_text = aData[2].trim();
      return row_text.match(new RegExp(filter_value, "i"));
    });

    /* check / uncheck all */
    function setSelected(checked) {
      $("input[name='object-selected']").prop("checked", checked);
    }

    $("a[href='#select-all']").click((e) => {
      setSelected(true);
      e.preventDefault();
    });

    $("a[href='#unselect-all']").click((e) => {
      setSelected(false);
      e.preventDefault();
    });

    /* actions */
    function onClickDelete(e) {
      e.preventDefault();
      const $button = $(this);
      const buttonForm = $(this.form);
      /* eslint-disable-next-line no-undef */
      let msg = CONFIG.deleteConfirmMsg;
      const elements = $(document.forms["folder-listing"])
        .find('input[name="object-selected"]:checked')
        .closest("td")
        .next("td");
      const elList = $("<ul />").attr({ class: "folder-items" });

      elements.each(function () {
        const li = $("<li />").html($(this).html());
        elList.append(li);
      });
      msg += $("<div />").append(elList).html();

      bootbox.confirm(msg, (confirm) => {
        if (confirm) {
          const actionVal = $("<input />", {
            type: "hidden",
            name: "action",
            value: $button.attr("value"),
          });
          buttonForm.append(actionVal);
          buttonForm.submit();
        }
      });
    }

    $('button.btn-danger[value="delete"]').click(onClickDelete);

    /* Move file functions */
    const moveFileFillListing = (modal, folder_url) => {
      const tbody = modal.find("tbody");
      const breadcrumbs = modal.find("ul.breadcrumb");

      $.ajax({
        type: "GET",
        dataType: "json",
        url: folder_url,
        cache: false,
        success(data) {
          const bc = $(data.breadcrumbs);
          breadcrumbs.empty();

          bc.each(function () {
            const li = $("<li />");
            const link = $("<a>" + this.title + "</a>")
              .attr("href", this.url)
              .attr("data-id", this.id);

            link.appendTo(li);
            li.appendTo(breadcrumbs);
          });

          const folders = $(data.folders);
          tbody.empty();

          folders.each(function () {
            const tr = $("<tr />");
            const td = $("<td />");
            const link = $("<a>" + this.title + "</a>")
              .attr("href", this.url)
              .attr("data-id", this.id);

            link.appendTo(td);
            td.append($("<span>/</span>").attr("class", "divider"));
            tr.append(td).appendTo(tbody);
          });

          const folderSelectable = data.current_folder_selectable;
          const button = $("#modal-move-button-submit");
          button.attr("disabled", !folderSelectable);
          if (!folderSelectable ^ button.hasClass("disabled")) {
            button.toggleClass("disabled");
          }
        },
      });
    };

    $(document).on(
      "click",
      "#modal-move-files-directory-listing a",
      function (e) {
        const self = $(this);
        const folder_id = self.attr("data-id");
        const modal = $("#modal-move-files");
        const url = self.attr("href");

        modal.find('input[name="target-folder"]').attr("value", folder_id);

        moveFileFillListing(modal, url);
        e.preventDefault();
      }
    );

    $("#modal-move-files").on("show.bs.modal", function () {
      const modal = $(this);
      const listing_form = $(document.forms["folder-listing"]);
      const elements = listing_form.find(
        "input[name='object-selected']:checked"
      );
      const footer_inputs = $("#modal-move-files-inputs");

      footer_inputs.empty();
      elements.clone().attr("type", "hidden").appendTo(footer_inputs);

      const target = $("<input />").attr({
        type: "hidden",
        name: "target-folder",
        value: "",
      });
      target.appendTo(footer_inputs);

      const l = document.location;
      /* don't use document.location + '/json': if anchors in url '/json'
             is ignored, ie http://.../folder#anchor */
      moveFileFillListing(
        modal,
        l.protocol + "//" + l.host + l.pathname + "/json" + l.search
      );
    });
  } // END setupFolderListing

  return setupFolderListing;
});
