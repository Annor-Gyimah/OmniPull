# def resume_btn(self):
    #     selected_row = widgets.table.currentRow()
    #     if selected_row < 0 or selected_row >= widgets.table.rowCount():
    #         self.show_warning(self.tr("Error"), self.tr("No download item selected"))
    #         return

    #     d_index = len(self.d_list) - 1 - selected_row
    #     d = self.d_list[d_index]

    #     if isinstance(d, Video):
    #         try:
    #             log(f"Refreshing YouTube video metadata before resuming {d.name}")
    #             d.update(d.url)         # Re-fetch fresh info from yt-dlp
    #             d.update_param()        # Rebuild temp files, segments, audio stream
    #         except Exception as e:
    #             log(f"Failed to refresh YouTube metadata: {e}")
    #             self.show_warning("Error", "Failed to refresh YouTube info. Try again or check your connection.")
    #             return

    #     self.start_download(d, silent=True)

    # def resume_btn(self):
    #     selected_row = widgets.table.currentRow()
    #     if selected_row < 0 or selected_row >= widgets.table.rowCount():
    #         self.show_warning(self.tr("Error"), self.tr("No download item selected"))
    #         return

    #     d_index = len(self.d_list) - 1 - selected_row
    #     d = self.d_list[d_index]



    #     self.start_download(d, silent=True)
    # def pause_btn(self):
    #     selected_row = widgets.table.currentRow()
    #     if selected_row < 0 or selected_row >= widgets.table.rowCount():
    #         self.show_warning(self.tr("Error"), self.tr("No download item selected"))
    #         return

    #     d_index = len(self.d_list) - 1 - selected_row
    #     d = self.d_list[d_index]

    #     if d.status == config.Status.completed:
    #         return

    #     d.status = config.Status.cancelled

    #     if d.status == config.Status.pending:
    #         self.pending.pop(d.id)



    # def pause_btn(self):
    #     selected_rows = widgets.table.selectionModel().selectedRows()
    #     if not selected_rows:
    #         return

    #     for row in selected_rows:
    #         row_index = row.row()
    #         id_item = widgets.table.item(row_index, 0)
    #         download_id = id_item.data(Qt.UserRole)

    #         # Find the matching download item
    #         d = next((x for x in self.d_list if x.id == download_id), None)
    #         if not d:
    #             continue

    #         # ✅ Case 1: It’s a queued item that is currently downloading
    #         if d.in_queue and d.queue_name and d.status == config.Status.downloading:
    #             log(f"[Pause] {d.name} is currently downloading in a queue. Setting back to queued.")
    #             d.status = config.Status.queued
    #             break  # ✅ Exit immediately to allow queue to resume the next one

    #         # ✅ Case 2: It's not part of a queue — just cancel it normally
    #         elif not d.in_queue and d.status in (config.Status.downloading, config.Status.pending):
    #             log(f"[Pause] {d.name} is a normal download. Cancelling.")
    #             d.status = config.Status.cancelled
    #             d.queue = ""
    #             d.queue_id = None
    #             d.queue_position = 0

    #             if d.status == config.Status.pending and d.id in self.pending:
    #                 self.pending.pop(d.id)

    #     setting.save_d_list(self.d_list)
    #     self.populate_table()




    # def stop_all_downloads(self):
    #     # change status of pending items to cancelled
    #     for d in self.d_list:
    #         if d.status in [config.Status.completed, config.Status.queued]:
    #             pass
    #         else:
    #             d.status = config.Status.cancelled

    #             self.pending.clear()

    # def resume_all_downloads(self):
    #     # change status of all non completed items to pending
    #     for d in self.d_list:
    #         if d.status == config.Status.cancelled:
    #             self.start_download(d, silent=True)
    # def schedule_all(self):
    #     try:
    #         response = ask_for_sched_time('Download scheduled for...')

    #         if response:
    #             for d in self.d_list:
    #                 if d.status in (config.Status.pending, config.Status.cancelled):
    #                     d.sched = response
    #                     log(f'Scheduled {d.name} for {response[0]}:{response[1]}')
    #     except Exception as e:
    #         log(f'Error in scheduling: {e}')