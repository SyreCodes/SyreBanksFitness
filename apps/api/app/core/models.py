"""Model registry used by Alembic; domain modules own their tables."""
from app.modules.admin.models import AuditLog
from app.modules.auth.models import ActionToken, EmailOutbox, RefreshSession, User
from app.modules.clients.models import ClientProfile, Consent
from app.modules.cms.models import BlogPost, MediaAsset, Setting
from app.modules.coaching.models import Exercise, Measurement, Program, ProgramAssignment, WorkoutSession
from app.modules.commerce.models import (
    Cart,
    CartItem,
    CommerceEvent,
    Course,
    CourseLesson,
    CourseModule,
    DigitalAsset,
    EntitlementGrant,
    ExchangeRate,
    Invoice,
    LessonProgress,
    Order,
    OrderItem,
    Payment,
    PaymentIntent,
    Product,
    ProductPrice,
    ProductTranslation,
    Subscription,
)
from app.modules.experience.models import Checkin, Habit, HabitLog, Message, Notification
from app.modules.feedback.models import FeedbackPost, FeedbackVote
from app.modules.formchecks.models import FormCheck
from app.modules.leads.models import Lead
from app.modules.scheduling.models import Booking

__all__ = ["ActionToken", "EmailOutbox", "AuditLog", "BlogPost", "Booking", "Cart", "CartItem", "Checkin", "ClientProfile", "CommerceEvent", "Consent", "Course", "CourseLesson", "CourseModule", "DigitalAsset", "EntitlementGrant", "ExchangeRate", "Exercise", "FeedbackPost", "FeedbackVote", "FormCheck", "Habit", "HabitLog", "Invoice", "Lead", "LessonProgress", "Measurement", "MediaAsset", "Message", "Notification", "Order", "OrderItem", "Payment", "PaymentIntent", "Product", "ProductPrice", "ProductTranslation", "Program", "ProgramAssignment", "RefreshSession", "Setting", "Subscription", "User", "WorkoutSession"]
