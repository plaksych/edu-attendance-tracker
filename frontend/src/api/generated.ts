// Generated from the current backend OpenAPI by openapi-typescript 7.13.0. Do not edit.
export interface paths {
    "/api/v1/admin/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Audit Events */
        get: operations["audit_events_api_v1_admin_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/system": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** System Status */
        get: operations["system_status_api_v1_admin_system_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Users */
        get: operations["users_api_v1_admin_users_get"];
        put?: never;
        /** Create User */
        post: operations["create_user_api_v1_admin_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update User */
        patch: operations["update_user_api_v1_admin_users__user_id__patch"];
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cameras": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить список камер
         * @description Возвращает камеры с замаскированными учётными данными в адресе.
         */
        get: operations["list_cameras_api_v1_cameras_get"];
        put?: never;
        /**
         * Создать камеру
         * @description Регистрирует камеру. `capture_group` определяет, какой capture-узел будет её опрашивать.
         */
        post: operations["create_camera_api_v1_cameras_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cameras/{camera_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Удалить камеру
         * @description Удаляет камеру без истории записей. Камеру с завершёнными или текущими заданиями следует отключить, чтобы сохранить историю.
         */
        delete: operations["delete_camera_api_v1_cameras__camera_id__delete"];
        options?: never;
        head?: never;
        /**
         * Изменить камеру
         * @description Частичное обновление. Адрес меняется только если поле `rtsp_url` передано.
         */
        patch: operations["update_camera_api_v1_cameras__camera_id__patch"];
        trace?: never;
    };
    "/api/v1/captures/{capture_id}/media": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить временные ссылки на медиа записи
         * @description Выдаёт presigned-ссылки MinIO на исходный ролик и размеченный кадр. После истечения срока хранения вместо ссылки возвращается причина недоступности.
         */
        get: operations["get_capture_media_api_v1_captures__capture_id__media_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/classrooms": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить список аудиторий
         * @description Возвращает аудитории с режимом объединения камер и привязанными камерами.
         */
        get: operations["list_classrooms_api_v1_classrooms_get"];
        put?: never;
        /**
         * Создать аудиторию
         * @description Создаёт аудиторию. Камеры привязываются отдельно через `PUT /classrooms/{id}/cameras`.
         */
        post: operations["create_classroom_api_v1_classrooms_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/classrooms/{classroom_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Изменить аудиторию
         * @description Частичное обновление вместимости и режима объединения камер.
         */
        patch: operations["update_classroom_api_v1_classrooms__classroom_id__patch"];
        trace?: never;
    };
    "/api/v1/classrooms/{classroom_id}/cameras": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Назначить камеры аудитории
         * @description Полностью заменяет набор камер аудитории. Штатно поддерживается не более двух камер; для режима primary_backup требуется ровно одна камера с ролью primary.
         */
        put: operations["assign_classroom_cameras_api_v1_classrooms__classroom_id__cameras_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/disciplines": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить список дисциплин
         * @description Возвращает дисциплины, отсортированные по названию.
         */
        get: operations["list_disciplines_api_v1_disciplines_get"];
        put?: never;
        /**
         * Создать дисциплину
         * @description Создаёт дисциплину для использования в расписании и статистике.
         */
        post: operations["create_discipline_api_v1_disciplines_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/groups": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить список групп
         * @description Возвращает учебные группы, отсортированные по названию.
         */
        get: operations["list_groups_api_v1_groups_get"];
        put?: never;
        /**
         * Создать группу
         * @description Создаёт учебную группу. `students_count` используется как ожидаемая численность при расчёте посещаемости.
         */
        post: operations["create_group_api_v1_groups_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/groups/{group_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Изменить группу
         * @description Частичное обновление: чаще всего используется для указания численности группы.
         */
        patch: operations["update_group_api_v1_groups__group_id__patch"];
        trace?: never;
    };
    "/api/v1/recognition/capabilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Capabilities */
        get: operations["capabilities_api_v1_recognition_capabilities_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/recognition/evaluation/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить качество по материалам с ручной разметкой
         * @description Считает ошибки только по завершённым загрузкам, в которых при создании задано эталонное число людей.
         */
        get: operations["get_evaluation_summary_api_v1_recognition_evaluation_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/recognition/uploads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить очередь загруженных файлов
         * @description Возвращает последние задания распознавания, включая состояние и результат.
         */
        get: operations["list_uploads_api_v1_recognition_uploads_get"];
        put?: never;
        /**
         * Загрузить видео или изображение для распознавания
         * @description Сохраняет файл в MinIO и создаёт задание для recognition-worker. Поддерживаются MP4, MOV, AVI, WebM, JPG, PNG и WebP. Видеофайл анализируется по выборке кадров, изображение — одним кадром.
         */
        post: operations["create_upload_api_v1_recognition_uploads_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/recognition/uploads/{upload_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Получить состояние задания распознавания */
        get: operations["get_upload_api_v1_recognition_uploads__upload_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/recognition/uploads/{upload_id}/corrections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Correct */
        post: operations["correct_api_v1_recognition_uploads__upload_id__corrections_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/recognition/uploads/{upload_id}/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** History */
        get: operations["history_api_v1_recognition_uploads__upload_id__history_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/recognition/uploads/{upload_id}/media": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Получить временные ссылки на файл и размеченный кадр */
        get: operations["get_upload_media_api_v1_recognition_uploads__upload_id__media_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/recognition/uploads/{upload_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry */
        post: operations["retry_api_v1_recognition_uploads__upload_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/schedule": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить расписание
         * @description Возвращает элементы расписания с вложенными справочниками. Можно фильтровать по группе, преподавателю и ISO-дню недели.
         */
        get: operations["list_schedule_api_v1_schedule_get"];
        put?: never;
        /**
         * Создать занятие в расписании
         * @description Добавляет одну запись расписания. Слот группы уникален по дню, времени начала и типу недели.
         */
        post: operations["create_schedule_item_api_v1_schedule_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/schedule/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Удалить запись расписания
         * @description Удаляет запись, у которой ещё нет созданных занятий. Записи с историей защищены от удаления, чтобы не потерять данные посещаемости.
         */
        delete: operations["delete_schedule_item_api_v1_schedule__item_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/schedule/calendar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Calendar */
        get: operations["list_calendar_api_v1_schedule_calendar_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/schedule/calendar/{day}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set Calendar */
        put: operations["set_calendar_api_v1_schedule_calendar__day__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/schedule/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Импортировать расписание из Excel
         * @description Принимает `.xlsx` и автоматически определяет формат: институтская сетка или простой построчный шаблон. Создаёт недостающие справочники и записи расписания.
         */
        post: operations["import_schedule_api_v1_schedule_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/schedule/import/{preview_id}/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Confirm Import */
        post: operations["confirm_import_api_v1_schedule_import__preview_id__confirm_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/schedule/import/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Import */
        post: operations["preview_import_api_v1_schedule_import_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/schedule/template": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Скачать Excel-шаблон расписания
         * @description Возвращает построчный `.xlsx`-шаблон для загрузки расписания через `/schedule/import`.
         */
        get: operations["download_template_api_v1_schedule_template_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/schedule/week-type": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Определить тип учебной недели
         * @description Возвращает белую или зелёную неделю для даты относительно `SEMESTER_START`.
         */
        get: operations["get_week_type_api_v1_schedule_week_type_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить занятия на дату
         * @description Возвращает созданные планировщиком занятия и их состояние; чтение не создаёт записи.
         */
        get: operations["list_by_date_api_v1_sessions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить занятие с деталями замеров
         * @description Возвращает занятие, оба замера, записи каждой камеры и результаты распознавания. Ссылки на медиа выдаются отдельно через `GET /captures/{id}/media`.
         */
        get: operations["get_session_api_v1_sessions__session_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/{session_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Отменить занятие
         * @description Отменяет занятие и все его незавершённые замеры и задания записи.
         */
        post: operations["cancel_session_api_v1_sessions__session_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/today": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить занятия на сегодня
         * @description Возвращает занятия текущей даты с состоянием обоих замеров и итогом посещаемости.
         */
        get: operations["list_today_api_v1_sessions_today_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stats/disciplines/{discipline_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить статистику дисциплины
         * @description Возвращает агрегаты дисциплины и разбивку по группам.
         */
        get: operations["get_discipline_stats_api_v1_stats_disciplines__discipline_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stats/export.csv": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Выгрузить агрегаты занятий без медиа и персональных результатов */
        get: operations["export_attendance_api_v1_stats_export_csv_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stats/groups/{group_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить статистику группы
         * @description Возвращает агрегаты группы и разбивку по дисциплинам.
         */
        get: operations["get_group_stats_api_v1_stats_groups__group_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stats/groups/{group_id}/timeline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить динамику посещаемости группы
         * @description Возвращает точки динамики по датам. Фильтры `date_from` и `date_to` ограничивают период.
         */
        get: operations["get_group_timeline_api_v1_stats_groups__group_id__timeline_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stats/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить сводку для дашборда
         * @description Возвращает общие счётчики и среднюю посещаемость по завершённым занятиям.
         */
        get: operations["get_summary_api_v1_stats_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stats/teachers/{teacher_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить статистику преподавателя
         * @description Возвращает агрегаты преподавателя и разбивку по группам.
         */
        get: operations["get_teacher_stats_api_v1_stats_teachers__teacher_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/teachers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Получить список преподавателей
         * @description Возвращает преподавателей, отсортированных по ФИО.
         */
        get: operations["list_teachers_api_v1_teachers_get"];
        put?: never;
        /**
         * Создать преподавателя
         * @description Создаёт преподавателя для дальнейшей привязки к расписанию.
         */
        post: operations["create_teacher_api_v1_teachers_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Проверить состояние backend
         * @description Возвращает `ok`, если backend-приложение запущено и отвечает на HTTP-запросы.
         */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ready */
        get: operations["ready_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** SessionRead */
        app__api__v1__auth__SessionRead: {
            /** Csrf Token */
            csrf_token: string;
            /** Enabled */
            enabled: boolean;
            /** Id */
            id: number;
            /**
             * Role
             * @enum {string}
             */
            role: "admin" | "operator" | "teacher" | "analyst";
            /** Username */
            username: string;
        };
        /** SessionRead */
        app__schemas__session__SessionRead: {
            attendance?: components["schemas"]["AttendanceRead"] | null;
            /**
             * Date
             * Format: date
             */
            date: string;
            /** Finished At */
            finished_at: string | null;
            /** Id */
            id: number;
            /** Measurements */
            measurements?: components["schemas"]["MeasurementRead"][];
            schedule: components["schemas"]["ScheduleRead"];
            /** Started At */
            started_at: string | null;
            status: components["schemas"]["SessionStatus"];
        };
        /**
         * AttendanceCalculationStatus
         * @description complete — оба замера успешны; partial — один; failed — ни одного.
         * @enum {string}
         */
        AttendanceCalculationStatus: "complete" | "partial" | "failed";
        /** AttendanceRead */
        AttendanceRead: {
            /**
             * After Start Count
             * @description Замер после начала занятия
             * @example 24
             */
            after_start_count: number | null;
            /**
             * Attendance Rate
             * @description Доля посещаемости от 0 до 1
             * @example 0.82
             */
            attendance_rate: number | null;
            /**
             * Before End Count
             * @description Замер перед концом занятия
             * @example 22
             */
            before_end_count: number | null;
            /** Calculated At */
            calculated_at: string | null;
            /** @description complete — оба замера, partial — один, failed — ни одного */
            calculation_status: components["schemas"]["AttendanceCalculationStatus"];
            /**
             * Detected Average
             * @description Среднее по успешным замерам
             * @example 23
             */
            detected_average: number | null;
            /**
             * Detected Max
             * @description Максимум по замерам
             * @example 24
             */
            detected_max: number | null;
            /**
             * Expected Count
             * @description Ожидаемая численность группы
             * @example 28
             */
            expected_count: number;
        };
        /** AuditRead */
        AuditRead: {
            /** Action */
            action: string;
            /** Actor Id */
            actor_id: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Id */
            id: number;
            /** Object Id */
            object_id: string | null;
            /** Object Type */
            object_type: string;
            /** Reason */
            reason: string | null;
            /** Request Id */
            request_id: string;
        };
        /** Body_create_upload_api_v1_recognition_uploads_post */
        Body_create_upload_api_v1_recognition_uploads_post: {
            /**
             * Confidence Threshold
             * @description Минимальная уверенность детектора
             * @default 0.35
             */
            confidence_threshold: number;
            /**
             * File
             * @description Видео или изображение
             */
            file: string;
            /**
             * Label
             * @description Краткое название материала для журнала проверки
             */
            label?: string | null;
            /** Measurement Id */
            measurement_id?: number | null;
            /**
             * Reference People Count
             * @description Число людей, вручную отмеченное на материале
             */
            reference_people_count?: number | null;
            /**
             * Sample Rate Fps
             * @description Кадров в секунду для видео; для изображения не используется
             * @default 1
             */
            sample_rate_fps: number;
            /** Session Id */
            session_id?: number | null;
        };
        /** Body_import_schedule_api_v1_schedule_import_post */
        Body_import_schedule_api_v1_schedule_import_post: {
            /** File */
            file: string;
        };
        /** Body_preview_import_api_v1_schedule_import_preview_post */
        Body_preview_import_api_v1_schedule_import_preview_post: {
            /** File */
            file: string;
        };
        /**
         * BreakdownItem
         * @description Строка разбивки: посещаемость в разрезе группы/дисциплины/преподавателя.
         */
        BreakdownItem: {
            /**
             * Avg Detected
             * @description Среднее число найденных людей
             * @example 23.4
             */
            avg_detected: number | null;
            /**
             * Avg Rate
             * @description Средняя посещаемость
             * @example 0.83
             */
            avg_rate: number | null;
            /**
             * Id
             * @description ID сущности в разбивке
             * @example 1
             */
            id: number;
            /**
             * Name
             * @description Название сущности в разбивке
             * @example Базы данных
             */
            name: string;
            /**
             * Sessions
             * @description Количество завершённых занятий
             * @example 14
             */
            sessions: number;
        };
        /** CalendarInput */
        CalendarInput: {
            /** Reason */
            reason: string;
            /**
             * Teaching
             * @default false
             */
            teaching: boolean;
            /** Week Type */
            week_type?: string | null;
            /** Weekday */
            weekday?: number | null;
        };
        /** CalendarRead */
        CalendarRead: {
            /**
             * Day
             * Format: date
             */
            day: string;
            /** Reason */
            reason: string;
            /**
             * Teaching
             * @default false
             */
            teaching: boolean;
            /** Week Type */
            week_type?: string | null;
            /** Weekday */
            weekday?: number | null;
        };
        /**
         * CameraAggregationMode
         * @description Как объединять результаты камер одной аудитории.
         *
         *     single         — одна камера;
         *     maximum        — зоны обзора пересекаются, берётся максимум;
         *     sum            — зоны не пересекаются, результаты суммируются;
         *     primary_backup — основная камера, резервная используется при сбое.
         * @enum {string}
         */
        CameraAggregationMode: "single" | "maximum" | "sum" | "primary_backup";
        /** CameraBrief */
        CameraBrief: {
            /** Id */
            id: number;
            /** Name */
            name: string;
        };
        /**
         * CameraCreate
         * @example {
         *       "capture_group": "building-a",
         *       "enabled": true,
         *       "name": "cam-302-front",
         *       "rtsp_url": "rtsp://user:password@192.168.1.10:554/stream1"
         *     }
         */
        CameraCreate: {
            /**
             * Capture Group
             * @description Сетевая зона или capture-узел, обслуживающий камеру
             * @default default
             * @example building-a
             */
            capture_group: string;
            /**
             * Enabled
             * @description Отключённая камера не участвует в замерах
             * @default true
             */
            enabled: boolean;
            /**
             * Name
             * @description Уникальное имя камеры
             * @example cam-302-front
             */
            name: string;
            /**
             * Rtsp Url
             * @description RTSP-адрес с IP из разрешённой администратором подсети
             * @example rtsp://user:password@192.168.1.10:554/stream1
             */
            rtsp_url: string;
        };
        /** CameraRead */
        CameraRead: {
            /**
             * Capture Group
             * @description Сетевая зона или capture-узел, обслуживающий камеру
             * @default default
             * @example building-a
             */
            capture_group: string;
            /**
             * Classroom Number
             * @description Аудитория, к которой привязана камера
             * @example 302
             */
            classroom_number?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Enabled
             * @description Отключённая камера не участвует в замерах
             * @default true
             */
            enabled: boolean;
            /** Id */
            id: number;
            /**
             * Name
             * @description Уникальное имя камеры
             * @example cam-302-front
             */
            name: string;
            /**
             * Rtsp Url
             * @description Всегда пустая строка: адрес и учётные данные не выдаются API
             * @example
             */
            rtsp_url: string;
        };
        /**
         * CameraRole
         * @enum {string}
         */
        CameraRole: "primary" | "secondary" | "backup";
        /** CameraUpdate */
        CameraUpdate: {
            /** Capture Group */
            capture_group?: string | null;
            /** Enabled */
            enabled?: boolean | null;
            /** Name */
            name?: string | null;
            /**
             * Rtsp Url
             * @description Новый адрес; если не передан, адрес не меняется
             */
            rtsp_url?: string | null;
        };
        /** CaptureMediaRead */
        CaptureMediaRead: {
            /** Annotated Unavailable Reason */
            annotated_unavailable_reason: string | null;
            /**
             * Annotated Url
             * @description Временная ссылка на размеченный кадр; null, если кадр недоступен
             */
            annotated_url: string | null;
            /**
             * Expires In Seconds
             * @description Срок действия выданных ссылок
             * @example 900
             */
            expires_in_seconds: number;
            /**
             * Video Unavailable Reason
             * @description Почему видео недоступно
             * @example медиа удалено по сроку хранения
             */
            video_unavailable_reason: string | null;
            /**
             * Video Url
             * @description Временная ссылка на исходный ролик; null, если видео недоступно
             */
            video_url: string | null;
        };
        /** CaptureRead */
        CaptureRead: {
            /** Attempts */
            attempts: number;
            camera: components["schemas"]["CameraBrief"];
            /**
             * Duration Ms
             * @description Длительность ролика, мс
             * @example 20000
             */
            duration_ms: number | null;
            /** Error */
            error: string | null;
            /**
             * Has Video
             * @description Записано ли исходное видео
             */
            readonly has_video: boolean;
            /** Id */
            id: number;
            /**
             * Planned At
             * Format: date-time
             */
            planned_at: string;
            /** Priority Snapshot */
            priority_snapshot?: number | null;
            result?: components["schemas"]["RecognitionResultRead"] | null;
            /** Role Snapshot */
            role_snapshot?: string | null;
            /**
             * Size Bytes
             * @description Размер записанного ролика
             * @example 2148000
             */
            size_bytes: number | null;
            /**
             * Snapshot Origin
             * @default unknown
             */
            snapshot_origin: string;
            status: components["schemas"]["CaptureStatus"];
            /** Zone Code Snapshot */
            zone_code_snapshot?: string | null;
        };
        /**
         * CaptureStatus
         * @enum {string}
         */
        CaptureStatus: "pending" | "claimed" | "recording" | "uploading" | "completed" | "retry_wait" | "failed" | "cancelled";
        /** ClassroomCameraAssign */
        ClassroomCameraAssign: {
            /**
             * Camera Id
             * @description ID камеры из справочника камер
             */
            camera_id: number;
            /**
             * Priority
             * @description Порядок предпочтения
             * @default 1
             */
            priority: number;
            /**
             * @description Роль камеры в аудитории
             * @default primary
             */
            role: components["schemas"]["CameraRole"];
            /**
             * Zone Code
             * @description Код зоны обзора для непересекающихся камер
             * @example left
             */
            zone_code?: string | null;
        };
        /** ClassroomCameraRead */
        ClassroomCameraRead: {
            camera: components["schemas"]["CameraBrief"];
            /**
             * Enabled
             * @description Текущее состояние камеры
             */
            enabled: boolean;
            /** Priority */
            priority: number;
            role: components["schemas"]["CameraRole"];
            /** Zone Code */
            zone_code: string | null;
        };
        /**
         * ClassroomCreate
         * @example {
         *       "aggregation_mode": "single",
         *       "capacity": 40,
         *       "number": "302"
         *     }
         */
        ClassroomCreate: {
            /**
             * @description Как объединять результаты камер: single — одна камера, maximum — пересекающиеся зоны, sum — непересекающиеся зоны, primary_backup — основная и резервная
             * @default single
             */
            aggregation_mode: components["schemas"]["CameraAggregationMode"];
            /**
             * Capacity
             * @description Вместимость аудитории
             * @example 40
             */
            capacity?: number | null;
            /**
             * Number
             * @description Номер или название аудитории
             * @example 302
             */
            number: string;
        };
        /** ClassroomRead */
        ClassroomRead: {
            /**
             * @description Как объединять результаты камер: single — одна камера, maximum — пересекающиеся зоны, sum — непересекающиеся зоны, primary_backup — основная и резервная
             * @default single
             */
            aggregation_mode: components["schemas"]["CameraAggregationMode"];
            /**
             * Cameras
             * @description Камеры аудитории с ролями и приоритетами
             */
            cameras?: components["schemas"]["ClassroomCameraRead"][];
            /**
             * Capacity
             * @description Вместимость аудитории
             * @example 40
             */
            capacity?: number | null;
            /** Id */
            id: number;
            /**
             * Number
             * @description Номер или название аудитории
             * @example 302
             */
            number: string;
        };
        /** ClassroomUpdate */
        ClassroomUpdate: {
            aggregation_mode?: components["schemas"]["CameraAggregationMode"] | null;
            /** Capacity */
            capacity?: number | null;
        };
        /** CorrectionCreated */
        CorrectionCreated: {
            /** Id */
            id: number;
            /** Job Id */
            job_id: number;
            /** People Count */
            people_count: number;
        };
        /** CorrectionInput */
        CorrectionInput: {
            /** People Count */
            people_count: number;
            /** Reason */
            reason: string;
        };
        /** CorrectionRead */
        CorrectionRead: {
            /** Actor Id */
            actor_id: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Id */
            id: number;
            /** Job Id */
            job_id: number;
            /** People Count */
            people_count: number;
            /** Reason */
            reason: string;
        };
        /**
         * DisciplineCreate
         * @example {
         *       "name": "Базы данных"
         *     }
         */
        DisciplineCreate: {
            /**
             * Name
             * @description Название дисциплины
             * @example Базы данных
             */
            name: string;
        };
        /** DisciplineRead */
        DisciplineRead: {
            /** Id */
            id: number;
            /**
             * Name
             * @description Название дисциплины
             * @example Базы данных
             */
            name: string;
        };
        /** EntityStats */
        EntityStats: {
            /**
             * Avg Detected
             * @description Среднее число найденных людей
             * @example 22.1
             */
            avg_detected: number | null;
            /**
             * Avg Rate
             * @description Средняя посещаемость
             * @example 0.79
             */
            avg_rate: number | null;
            /**
             * Breakdown
             * @description Разбивка по связанным сущностям
             */
            breakdown: components["schemas"]["BreakdownItem"][];
            /**
             * Id
             * @description ID выбранной сущности
             * @example 1
             */
            id: number;
            /**
             * Name
             * @description Название выбранной сущности
             * @example ИВТ-21
             */
            name: string;
            /**
             * Records Complete
             * @description Занятий с двумя успешными замерами
             * @example 28
             */
            records_complete: number;
            /**
             * Records Failed
             * @description Занятий без успешных замеров
             * @example 1
             */
            records_failed: number;
            /**
             * Records Partial
             * @description Занятий с одним успешным замером
             * @example 3
             */
            records_partial: number;
            /**
             * Sessions Finished
             * @description Количество завершённых занятий
             * @example 32
             */
            sessions_finished: number;
        };
        /**
         * GroupCreate
         * @example {
         *       "course": 2,
         *       "faculty": "Институт компьютерных наук",
         *       "name": "ИВТ-21",
         *       "students_count": 28
         *     }
         */
        GroupCreate: {
            /**
             * Course
             * @description Курс обучения
             * @default 1
             * @example 2
             */
            course: number;
            /**
             * Faculty
             * @description Факультет или институт
             * @example Институт компьютерных наук
             */
            faculty?: string | null;
            /**
             * Name
             * @description Название учебной группы
             * @example ИВТ-21
             */
            name: string;
            /**
             * Students Count
             * @description Численность группы для расчёта процента посещаемости
             * @default 0
             * @example 28
             */
            students_count: number;
        };
        /** GroupRead */
        GroupRead: {
            /**
             * Course
             * @description Курс обучения
             * @default 1
             * @example 2
             */
            course: number;
            /**
             * Faculty
             * @description Факультет или институт
             * @example Институт компьютерных наук
             */
            faculty?: string | null;
            /** Id */
            id: number;
            /**
             * Name
             * @description Название учебной группы
             * @example ИВТ-21
             */
            name: string;
            /**
             * Students Count
             * @description Численность группы для расчёта процента посещаемости
             * @default 0
             * @example 28
             */
            students_count: number;
        };
        /** GroupTimeline */
        GroupTimeline: {
            /**
             * Group Id
             * @description ID группы
             * @example 1
             */
            group_id: number;
            /**
             * Group Name
             * @description Название группы
             * @example ИВТ-21
             */
            group_name: string;
            /**
             * Points
             * @description Точки временного ряда
             */
            points: components["schemas"]["TimelinePoint"][];
        };
        /** GroupUpdate */
        GroupUpdate: {
            /** Course */
            course?: number | null;
            /** Faculty */
            faculty?: string | null;
            /**
             * Students Count
             * @description Численность группы; влияет на расчёт attendance_rate
             */
            students_count?: number | null;
        };
        /** HealthRead */
        HealthRead: {
            /**
             * Status
             * @description Состояние сервиса
             * @example ok
             */
            status: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** ImportPreviewRead */
        ImportPreviewRead: {
            /** Created */
            created: number;
            /** Errors */
            errors: string[];
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Preview Id */
            preview_id: string;
            /** Rows */
            rows: components["schemas"]["Lesson"][];
            /** Skipped */
            skipped: number;
        };
        /** Lesson */
        Lesson: {
            /** Classroom */
            classroom?: string | null;
            /** Discipline */
            discipline: string;
            /**
             * Ends At
             * Format: time
             */
            ends_at: string;
            /** Group */
            group: string;
            /** Lesson Type */
            lesson_type?: string | null;
            /**
             * Starts At
             * Format: time
             */
            starts_at: string;
            /** Teacher */
            teacher?: string | null;
            /** @default every */
            week_type: components["schemas"]["WeekType"];
            /** Weekday */
            weekday: number;
        };
        /** LoginInput */
        LoginInput: {
            /** Password */
            password: string;
            /** Username */
            username: string;
        };
        /** MeasurementDetail */
        MeasurementDetail: {
            aggregation_method: components["schemas"]["CameraAggregationMode"];
            /** Captures */
            captures: components["schemas"]["CaptureRead"][];
            /**
             * Confidence
             * @description Уверенность итога
             * @example 0.82
             */
            confidence: number | null;
            /** Error */
            error: string | null;
            /**
             * Final People Count
             * @description Итог замера после объединения камер
             * @example 24
             */
            final_people_count: number | null;
            /** Id */
            id: number;
            /**
             * Planned At
             * Format: date-time
             */
            planned_at: string;
            /** Provenance */
            readonly provenance: string;
            /** Source Reference Status */
            source_reference_status?: string | null;
            /** Source Results */
            source_results?: components["schemas"]["MeasurementResultSourceRead"][];
            status: components["schemas"]["MeasurementStatus"];
            /** @description after_start — через 15 минут после начала, before_end — за 15 минут до конца */
            type: components["schemas"]["MeasurementType"];
        };
        /** MeasurementRead */
        MeasurementRead: {
            aggregation_method: components["schemas"]["CameraAggregationMode"];
            /**
             * Confidence
             * @description Уверенность итога
             * @example 0.82
             */
            confidence: number | null;
            /** Error */
            error: string | null;
            /**
             * Final People Count
             * @description Итог замера после объединения камер
             * @example 24
             */
            final_people_count: number | null;
            /** Id */
            id: number;
            /**
             * Planned At
             * Format: date-time
             */
            planned_at: string;
            /** Provenance */
            readonly provenance: string;
            /** Source Reference Status */
            source_reference_status?: string | null;
            /** Source Results */
            source_results?: components["schemas"]["MeasurementResultSourceRead"][];
            status: components["schemas"]["MeasurementStatus"];
            /** @description after_start — через 15 минут после начала, before_end — за 15 минут до конца */
            type: components["schemas"]["MeasurementType"];
        };
        /** MeasurementResultSourceRead */
        MeasurementResultSourceRead: {
            /** Camera Capture Id */
            camera_capture_id?: number | null;
            /** People Count */
            people_count?: number | null;
            /** Recognition Job Id */
            recognition_job_id?: number | null;
            /** Recognition Result Id */
            recognition_result_id: number;
            /** Upload Id */
            upload_id?: number | null;
            /**
             * Used For Count
             * @default true
             */
            used_for_count: boolean;
        };
        /**
         * MeasurementStatus
         * @enum {string}
         */
        MeasurementStatus: "scheduled" | "capturing" | "recognizing" | "completed" | "partially_completed" | "failed" | "cancelled";
        /**
         * MeasurementType
         * @description after_start — через 15 минут после начала; before_end — за 15 минут до конца.
         * @enum {string}
         */
        MeasurementType: "after_start" | "before_end";
        /** ParameterRange */
        ParameterRange: {
            /** Max */
            max: number;
            /** Min */
            min: number;
        };
        /** RecognitionCapabilities */
        RecognitionCapabilities: {
            confidence: components["schemas"]["ParameterRange"];
            /** Formats */
            formats: string[];
            /** Max Duration Seconds */
            max_duration_seconds: number;
            /** Max Pixels */
            max_pixels: number;
            /** Max Size Bytes */
            max_size_bytes: number;
            /** Max Video Dimension */
            max_video_dimension: number;
            /**
             * Profile
             * @constant
             */
            profile: "server_inference";
            sample_rate_fps: components["schemas"]["ParameterRange"];
        };
        /** RecognitionEvaluationSummary */
        RecognitionEvaluationSummary: {
            /**
             * Checked Materials
             * @description Число материалов с ручным эталоном
             */
            checked_materials: number;
            /**
             * Max Absolute Error
             * @description Максимальная абсолютная ошибка
             */
            max_absolute_error: number | null;
            /**
             * Mean Absolute Error
             * @description Средняя абсолютная ошибка
             */
            mean_absolute_error: number | null;
            /**
             * Mean Relative Error
             * @description Средняя относительная ошибка
             */
            mean_relative_error: number | null;
            /**
             * Median Absolute Error
             * @description Медианная абсолютная ошибка
             */
            median_absolute_error: number | null;
            /**
             * Within Tolerance Count
             * @description Число результатов в допустимой ошибке
             */
            within_tolerance_count: number;
        };
        /** RecognitionHistoryRead */
        RecognitionHistoryRead: {
            /** Corrections */
            corrections: components["schemas"]["CorrectionRead"][];
            /** Jobs */
            jobs: components["schemas"]["RecognitionUploadJobRead"][];
        };
        /**
         * RecognitionMediaType
         * @description Тип входного файла для самостоятельного задания распознавания.
         * @enum {string}
         */
        RecognitionMediaType: "image" | "video";
        /** RecognitionResultRead */
        RecognitionResultRead: {
            /**
             * Absolute Error
             * @description Абсолютная ошибка относительно ручного эталона
             * @example 1
             */
            absolute_error: number | null;
            /**
             * Average Confidence
             * @description Средняя уверенность детектора
             * @example 0.82
             */
            average_confidence: number | null;
            /**
             * Count Stddev
             * @description Стандартное отклонение числа людей по кадрам
             * @example 0.5
             */
            count_stddev: number;
            /**
             * Detected Max
             * @description Максимум по кадрам
             * @example 26
             */
            detected_max: number;
            /**
             * Detected Median
             * @description Медиана по кадрам
             * @example 24
             */
            detected_median: number;
            /**
             * Detected Percentile 75
             * @description 75-й перцентиль по кадрам
             * @example 25
             */
            detected_percentile_75: number;
            /** Inference Metadata */
            inference_metadata?: {
                [key: string]: unknown;
            } | null;
            /**
             * Media Expires At
             * @description Когда размеченный кадр будет удалён по сроку хранения
             */
            media_expires_at: string | null;
            /**
             * People Count
             * @description Итоговое количество людей на ролике
             * @example 24
             */
            people_count: number;
            /**
             * Relative Error
             * @description Относительная ошибка относительно ручного эталона
             * @example 0.04
             */
            relative_error: number | null;
            /**
             * Representative Frame Ms
             * @description Позиция репрезентативного кадра в ролике, мс
             * @example 9500
             */
            representative_frame_ms: number;
            /**
             * Sampled Frames
             * @description Число проанализированных кадров
             * @example 20
             */
            sampled_frames: number;
            /**
             * Source Duration Ms
             * @description Длительность исходного видео, мс
             * @example 30000
             */
            source_duration_ms: number;
            /**
             * Source Frames
             * @description Число кадров в исходном видео
             * @example 750
             */
            source_frames: number;
            /**
             * Within Tolerance
             * @description Укладывается ли ошибка в допустимое число человек
             */
            within_tolerance: boolean | null;
        };
        /**
         * RecognitionStatus
         * @enum {string}
         */
        RecognitionStatus: "pending" | "processing" | "retry_wait" | "completed" | "failed" | "cancelled";
        /** RecognitionUploadJobRead */
        RecognitionUploadJobRead: {
            /** Attempts */
            attempts: number;
            /**
             * Confidence Threshold
             * @description Минимальная уверенность детектора
             * @example 0.35
             */
            confidence_threshold: number;
            /** Error */
            error: string | null;
            /** Finished At */
            finished_at: string | null;
            /** Id */
            id: number;
            /** Model Name */
            model_name: string;
            /** Model Version */
            model_version: string;
            result?: components["schemas"]["RecognitionResultRead"] | null;
            /**
             * Sample Rate Fps
             * @description Частота выборки кадров у видео
             * @example 1
             */
            sample_rate_fps: number;
            /** Started At */
            started_at: string | null;
            status: components["schemas"]["RecognitionStatus"];
        };
        /** RecognitionUploadMediaRead */
        RecognitionUploadMediaRead: {
            /** Annotated Unavailable Reason */
            annotated_unavailable_reason: string | null;
            /**
             * Annotated Url
             * @description Временная ссылка на размеченный кадр
             */
            annotated_url: string | null;
            /**
             * Expires In Seconds
             * @description Срок действия выданных ссылок
             * @example 900
             */
            expires_in_seconds: number;
            /** Source Unavailable Reason */
            source_unavailable_reason: string | null;
            /**
             * Source Url
             * @description Временная ссылка на загруженный исходный файл
             */
            source_url: string | null;
        };
        /** RecognitionUploadRead */
        RecognitionUploadRead: {
            /** Content Type */
            content_type: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Filename */
            filename: string;
            /** Id */
            id: number;
            job: components["schemas"]["RecognitionUploadJobRead"];
            /**
             * Label
             * @description Краткое название проверочного материала
             */
            label: string | null;
            /** Measurement Id */
            measurement_id?: number | null;
            media_type: components["schemas"]["RecognitionMediaType"];
            /**
             * Provenance
             * @default server_inference
             */
            provenance: string;
            /**
             * Reference People Count
             * @description Ручной эталон для расчёта ошибки
             * @example 8
             */
            reference_people_count: number | null;
            /** Session Id */
            session_id?: number | null;
            /** Size Bytes */
            size_bytes: number;
        };
        /**
         * ScheduleCreate
         * @example {
         *       "classroom_id": 1,
         *       "discipline_id": 1,
         *       "ends_at": "10:30:00",
         *       "group_id": 1,
         *       "lesson_type": "лек.",
         *       "starts_at": "09:00:00",
         *       "teacher_id": 1,
         *       "week_type": "every",
         *       "weekday": 1
         *     }
         */
        ScheduleCreate: {
            /**
             * Classroom Id
             * @description ID аудитории. Если аудитория не указана, запуск камеры невозможен.
             * @example 1
             */
            classroom_id?: number | null;
            /**
             * Discipline Id
             * @description ID дисциплины
             * @example 1
             */
            discipline_id: number;
            /**
             * Ends At
             * Format: time
             * @description Время окончания занятия
             * @example 10:30:00
             */
            ends_at: string;
            /**
             * Group Id
             * @description ID учебной группы
             * @example 1
             */
            group_id: number;
            /**
             * Lesson Type
             * @description Тип занятия из расписания: лек., пр., лаб.
             * @example лек.
             */
            lesson_type?: string | null;
            /**
             * Starts At
             * Format: time
             * @description Время начала занятия
             * @example 09:00:00
             */
            starts_at: string;
            /**
             * Teacher Id
             * @description ID преподавателя. Может отсутствовать в исходном расписании.
             * @example 1
             */
            teacher_id?: number | null;
            /**
             * @description Тип недели: каждую неделю, белая или зелёная
             * @default every
             */
            week_type: components["schemas"]["WeekType"];
            /**
             * Weekday
             * @description ISO-день недели: 1 — понедельник, 7 — воскресенье
             * @example 1
             */
            weekday: number;
        };
        /** ScheduleImportResult */
        ScheduleImportResult: {
            /**
             * Created
             * @description Количество созданных записей расписания
             * @example 42
             */
            created: number;
            /**
             * Errors
             * @description Ошибки по строкам или ячейкам, которые не удалось импортировать
             * @example [
             *       "Строка 8: не указана дисциплина"
             *     ]
             */
            errors: string[];
            /**
             * Skipped
             * @description Количество пропущенных дублей
             * @example 3
             */
            skipped: number;
        };
        /** ScheduleRead */
        ScheduleRead: {
            classroom: components["schemas"]["ClassroomRead"] | null;
            discipline: components["schemas"]["DisciplineRead"];
            /**
             * Ends At
             * Format: time
             */
            ends_at: string;
            group: components["schemas"]["GroupRead"];
            /** Id */
            id: number;
            /** Lesson Type */
            lesson_type: string | null;
            /**
             * Starts At
             * Format: time
             */
            starts_at: string;
            teacher: components["schemas"]["TeacherRead"] | null;
            week_type: components["schemas"]["WeekType"];
            /** Weekday */
            weekday: number;
        };
        /** SessionDetail */
        SessionDetail: {
            attendance?: components["schemas"]["AttendanceRead"] | null;
            /**
             * Date
             * Format: date
             */
            date: string;
            /** Finished At */
            finished_at: string | null;
            /** Id */
            id: number;
            /** Measurements */
            measurements?: components["schemas"]["MeasurementDetail"][];
            schedule: components["schemas"]["ScheduleRead"];
            /** Started At */
            started_at: string | null;
            status: components["schemas"]["SessionStatus"];
        };
        /**
         * SessionStatus
         * @enum {string}
         */
        SessionStatus: "scheduled" | "in_progress" | "finished" | "cancelled";
        /** SummaryStats */
        SummaryStats: {
            /**
             * Avg Attendance Rate
             * @description Средняя посещаемость по завершённым занятиям
             * @example 0.81
             */
            avg_attendance_rate: number | null;
            /**
             * Cameras
             * @description Количество камер
             * @example 14
             */
            cameras: number;
            /**
             * Classrooms
             * @description Количество аудиторий
             * @example 10
             */
            classrooms: number;
            /**
             * Disciplines
             * @description Количество дисциплин
             * @example 18
             */
            disciplines: number;
            /**
             * Groups
             * @description Количество групп
             * @example 12
             */
            groups: number;
            /**
             * Records Complete
             * @description Занятий с двумя успешными замерами
             * @example 48
             */
            records_complete: number;
            /**
             * Records Failed
             * @description Занятий без успешных замеров
             * @example 2
             */
            records_failed: number;
            /**
             * Records Partial
             * @description Занятий с одним успешным замером
             * @example 6
             */
            records_partial: number;
            /**
             * Sessions Finished
             * @description Завершённых занятий
             * @example 56
             */
            sessions_finished: number;
            /**
             * Sessions Today
             * @description Занятий на текущую дату
             * @example 8
             */
            sessions_today: number;
            /**
             * Sessions Total
             * @description Всего сформированных занятий
             * @example 120
             */
            sessions_total: number;
            /**
             * Teachers
             * @description Количество преподавателей
             * @example 24
             */
            teachers: number;
        };
        /** SystemRead */
        SystemRead: {
            /**
             * Backup Status
             * @constant
             */
            backup_status: "not_verified";
            /** Camera Enabled */
            camera_enabled: boolean;
            /**
             * Database
             * @constant
             */
            database: "ready";
            /** Environment */
            environment: string;
            /** Last Job Heartbeat */
            last_job_heartbeat: string | null;
            /** Recognition Queue */
            recognition_queue: {
                [key: string]: number;
            };
            /**
             * Storage
             * @enum {string}
             */
            storage: "ready" | "unavailable";
            /** Timezone */
            timezone: string;
        };
        /**
         * TeacherCreate
         * @example {
         *       "department": "Кафедра информационных систем",
         *       "email": "ivanov@example.edu",
         *       "full_name": "Иванов Иван Иванович"
         *     }
         */
        TeacherCreate: {
            /**
             * Department
             * @description Кафедра или подразделение
             * @example Кафедра информационных систем
             */
            department?: string | null;
            /**
             * Email
             * @description Контактный email преподавателя
             * @example ivanov@example.edu
             */
            email?: string | null;
            /**
             * Full Name
             * @description ФИО преподавателя
             * @example Иванов Иван Иванович
             */
            full_name: string;
        };
        /** TeacherRead */
        TeacherRead: {
            /**
             * Department
             * @description Кафедра или подразделение
             * @example Кафедра информационных систем
             */
            department?: string | null;
            /**
             * Email
             * @description Контактный email преподавателя
             * @example ivanov@example.edu
             */
            email?: string | null;
            /**
             * Full Name
             * @description ФИО преподавателя
             * @example Иванов Иван Иванович
             */
            full_name: string;
            /** Id */
            id: number;
        };
        /** TimelinePoint */
        TimelinePoint: {
            /**
             * Avg Detected
             * @description Среднее число найденных людей за дату
             * @example 24.2
             */
            avg_detected: number | null;
            /**
             * Avg Rate
             * @description Средняя посещаемость за дату
             * @example 0.86
             */
            avg_rate: number | null;
            /**
             * Date
             * Format: date
             * @description Дата занятий
             * @example 2026-07-04
             */
            date: string;
            /**
             * Expected
             * @description Ожидаемая численность группы
             * @example 28
             */
            expected: number | null;
        };
        /** UserInput */
        UserInput: {
            /** Password */
            password: string;
            /** Role */
            role: string;
            /** Username */
            username: string;
        };
        /** UserRead */
        UserRead: {
            /** Enabled */
            enabled: boolean;
            /** Id */
            id: number;
            /**
             * Role
             * @enum {string}
             */
            role: "admin" | "operator" | "teacher" | "analyst";
            /** Username */
            username: string;
        };
        /** UserUpdate */
        UserUpdate: {
            /** Enabled */
            enabled?: boolean | null;
            /** Group Ids */
            group_ids?: number[] | null;
            /** Password */
            password?: string | null;
            /** Reason */
            reason: string;
            /** Role */
            role?: string | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /**
         * WeekType
         * @description Чередование недель: пара идёт каждую неделю, только по белым или только по зелёным.
         * @enum {string}
         */
        WeekType: "every" | "white" | "green";
        /** WeekTypeRead */
        WeekTypeRead: {
            /**
             * Date
             * Format: date
             * @description Дата проверки
             * @example 2026-02-09
             */
            date: string;
            /** @description Тип учебной недели */
            week_type: components["schemas"]["WeekType"];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    audit_events_api_v1_admin_audit_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    system_status_api_v1_admin_system_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SystemRead"];
                };
            };
        };
    };
    users_api_v1_admin_users_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_user_api_v1_admin_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_user_api_v1_admin_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__api__v1__auth__SessionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    me_api_v1_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__api__v1__auth__SessionRead"];
                };
            };
        };
    };
    list_cameras_api_v1_cameras_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CameraRead"][];
                };
            };
        };
    };
    create_camera_api_v1_cameras_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CameraCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CameraRead"];
                };
            };
            /** @description Камера с таким именем уже существует */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_camera_api_v1_cameras__camera_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                camera_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Камера не найдена */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description У камеры есть задания записи в истории */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_camera_api_v1_cameras__camera_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                camera_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CameraUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CameraRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_capture_media_api_v1_captures__capture_id__media_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                capture_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaptureMediaRead"];
                };
            };
            /** @description Запись не найдена */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_classrooms_api_v1_classrooms_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClassroomRead"][];
                };
            };
        };
    };
    create_classroom_api_v1_classrooms_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClassroomCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClassroomRead"];
                };
            };
            /** @description Запись с таким уникальным значением уже существует */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_classroom_api_v1_classrooms__classroom_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                classroom_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClassroomUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClassroomRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    assign_classroom_cameras_api_v1_classrooms__classroom_id__cameras_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                classroom_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClassroomCameraAssign"][];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClassroomRead"];
                };
            };
            /** @description Камера уже привязана к другой аудитории */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Набор камер противоречит режиму объединения */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    list_disciplines_api_v1_disciplines_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DisciplineRead"][];
                };
            };
        };
    };
    create_discipline_api_v1_disciplines_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DisciplineCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DisciplineRead"];
                };
            };
            /** @description Запись с таким уникальным значением уже существует */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_groups_api_v1_groups_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupRead"][];
                };
            };
        };
    };
    create_group_api_v1_groups_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroupCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupRead"];
                };
            };
            /** @description Запись с таким уникальным значением уже существует */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_group_api_v1_groups__group_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroupUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    capabilities_api_v1_recognition_capabilities_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionCapabilities"];
                };
            };
        };
    };
    get_evaluation_summary_api_v1_recognition_evaluation_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionEvaluationSummary"];
                };
            };
        };
    };
    list_uploads_api_v1_recognition_uploads_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionUploadRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_upload_api_v1_recognition_uploads_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_create_upload_api_v1_recognition_uploads_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionUploadRead"];
                };
            };
            /** @description Размер файла превышает лимит */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_upload_api_v1_recognition_uploads__upload_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionUploadRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    correct_api_v1_recognition_uploads__upload_id__corrections_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorrectionInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CorrectionCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    history_api_v1_recognition_uploads__upload_id__history_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionHistoryRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_upload_media_api_v1_recognition_uploads__upload_id__media_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionUploadMediaRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_api_v1_recognition_uploads__upload_id__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecognitionUploadRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_schedule_api_v1_schedule_get: {
        parameters: {
            query?: {
                /** @description ID учебной группы */
                group_id?: number | null;
                /** @description ID преподавателя */
                teacher_id?: number | null;
                /** @description ISO-день недели: 1 — понедельник, 7 — воскресенье */
                weekday?: number | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_schedule_item_api_v1_schedule_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScheduleCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleRead"];
                };
            };
            /** @description Слот уже занят или указаны несуществующие справочники */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_schedule_item_api_v1_schedule__item_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Запись расписания не найдена */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Для записи уже есть занятия в истории */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_calendar_api_v1_schedule_calendar_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarRead"][];
                };
            };
        };
    };
    set_calendar_api_v1_schedule_calendar__day__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                day: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CalendarInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_schedule_api_v1_schedule_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_import_schedule_api_v1_schedule_import_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleImportResult"];
                };
            };
            /** @description Файл не является `.xlsx` или содержит некорректные данные */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirm_import_api_v1_schedule_import__preview_id__confirm_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                preview_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScheduleImportResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_import_api_v1_schedule_import_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_preview_import_api_v1_schedule_import_preview_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportPreviewRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_template_api_v1_schedule_template_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Excel-файл с шаблоном расписания */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": unknown;
                };
            };
        };
    };
    get_week_type_api_v1_schedule_week_type_get: {
        parameters: {
            query?: {
                /** @description Дата проверки. Если не указана, используется текущая дата. */
                date?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WeekTypeRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_by_date_api_v1_sessions_get: {
        parameters: {
            query: {
                /** @description Дата занятий */
                date: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__schemas__session__SessionRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_session_api_v1_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionDetail"];
                };
            };
            /** @description Занятие не найдено */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_session_api_v1_sessions__session_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__schemas__session__SessionRead"];
                };
            };
            /** @description Занятие уже завершено или отменено */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_today_api_v1_sessions_today_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__schemas__session__SessionRead"][];
                };
            };
        };
    };
    get_discipline_stats_api_v1_stats_disciplines__discipline_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                discipline_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EntityStats"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_attendance_api_v1_stats_export_csv_get: {
        parameters: {
            query: {
                date_from: string;
                date_to: string;
                group_id?: number | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_group_stats_api_v1_stats_groups__group_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EntityStats"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_group_timeline_api_v1_stats_groups__group_id__timeline_get: {
        parameters: {
            query?: {
                /** @description Начальная дата периода */
                date_from?: string | null;
                /** @description Конечная дата периода */
                date_to?: string | null;
            };
            header?: never;
            path: {
                group_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupTimeline"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_summary_api_v1_stats_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SummaryStats"];
                };
            };
        };
    };
    get_teacher_stats_api_v1_stats_teachers__teacher_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                teacher_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EntityStats"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_teachers_api_v1_teachers_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeacherRead"][];
                };
            };
        };
    };
    create_teacher_api_v1_teachers_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TeacherCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeacherRead"];
                };
            };
            /** @description Запись с таким уникальным значением уже существует */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthRead"];
                };
            };
        };
    };
    ready_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
}
