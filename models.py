from django.db import models
from django.db.models import Max
from django.db.models import F, Q
from datetime import datetime

# Create your models here.

class Bracket(models.Model):
    # [12m_Competitor]
    # [12m_Judge]
    # [12m_Bout]
    name = models.CharField(max_length=30, null=True, blank=True)
    description = models.CharField(max_length=100, null=True, blank=True)
    manager = models.CharField(max_length=30, null=True, blank=True)
    ready = models.NullBooleanField()
    finished = models.NullBooleanField()

    def get_bout(self, judge):
        pass
        # check if judge is eligable to make decisions
        # return choices 
        # use manager to decide next set of bouts
        # eval(self.manager).repair()

class Competitor(models.Model):
    # [12m_Bout]
    bracket = models.ForeignKey(Bracket)
    name = models.CharField(max_length=30, null=True, blank=True)
    game = models.TextField(null=True, blank=True)
    wins = models.IntegerField(null=True, blank=True)
    losses = models.IntegerField(null=True, blank=True)
    points = models.IntegerField(null=True, blank=True)
    byes = models.IntegerField(null=True, blank=True)
    status = models.IntegerField(null=True, blank=True)

class Judge(models.Model):
    # [12m_Bout]
    bracket = models.ForeignKey(Bracket)
    name = models.CharField(max_length=30, null=True, blank=True)
    eligable = models.IntegerField(null=True, blank=True)
    decisions = models.IntegerField(null=True, blank=True)

class Bout(models.Model):
    bracket = models.ForeignKey(Bracket)
    bround = models.IntegerField(null=True, blank=True)
    judge = models.ForeignKey(Judge, null=True)
    compA = models.ForeignKey(Competitor, related_name='compA')
    compB = models.ForeignKey(Competitor, related_name='compB')
    winner = models.ForeignKey(Competitor, related_name='winner', null=True)
    btime = models.DateTimeField(null=True, blank=True)


class Base_Tourney(object):

    def __init__(self, bracket):
        self.bracket = bracket

    def Register(self, name, game):
        if not self.bracket.ready:
            cc = Competitor.objects.get_or_create(bracket=self.bracket, name=name)[0]
            cc.game = game
            cc.save()

    def Game(self, competitor):
        try:  
            return Competitor.objects.get(bracket=self.bracket, name=competitor.username).game
        except:
            return ""

    def Setup(self, who):
        # cascade events
        self.Round_Cleanup() 
        if self.bracket.finished:
            return
        judge = self.Get_Judge(who)
        if self.Round_Complete(judge):
            self.Advancing()
            self.RePair(who)

    def Get_Judge(self, who):
        # get judge object for voter
        try:
            judge = Judge.objects.get(bracket=self.bracket, name=who)
            return judge
        except:
            return False

    def Round_Cleanup(self):
        # if there aren't any judgements left we're done (plus clean up party trash)
        judgements = self.bracket.judge_set.filter(eligable__gt=F('decisions'))
        if len(judgements) == 0:
            self.bracket.finished = 1
            self.bracket.save()
            # find all the dangling bouts (party trash) and delete them
            Bout.objects.filter(bracket=self.bracket, winner__isnull=True).delete()
            return 

        # remove dangling vote assignments
        # look up all active vote assignments for this bracket
        # spin over and clear any that are older than 15 minutes
        dangling = Bout.objects.filter(bracket=self.bracket, winner__isnull=True, btime__isnull=False)
        for bb in dangling:
            del_minutes = (datetime.now() - bb.btime).seconds / 60
            if del_minutes >= 15:
                bb.delete()

    def Round_Complete(self, judge):
        # check if there are any bouts remaining in current/last round
        all_rounds = self.bracket.bout_set.all()
        if len(all_rounds) == 0:
            return True
        last_round = all_rounds.aggregate(Max('bround'))
        current_round = last_round['bround__max']
        remain = all_rounds.filter(bround=current_round, winner__isnull=True)
        #remain = all_rounds.filter(~Q(judge=judge), bround=current_round, winner__isnull=True)
        return (len(remain) == 0)

    def RePair(self, who):
        pass

    def Advancing(self):
        # only winners advance in single elimination
        pass 

    def Get_Next_Round_Number(self):
        # assumes last round is complete 
        all_rounds = self.bracket.bout_set.all()
        # no bouts yet means first round
        if len(all_rounds) == 0:
            return 1
        last_round = all_rounds.aggregate(Max('bround'))
        return (last_round['bround__max'] + 1)

    def Status(self, who):
        if not self.Status_Participating(who):
            return "MESSAGE_NON_PART"
        elif self.Status_Wait(who):
            return "MESSAGE_WAIT"
        elif self.Status_Vote_Ready(who):
            return "MESSAGE_VOTE"
        elif self.Status_Vote_Done(who): 
            return "MESSAGE_THANKS"
        else:
            return "MESSAGE_WINNER"

    def GetWinner(self):
        try:
            winner = self.bracket.competitor_set.filter(status=1)[0].game
        except:
            winner = 0
        # wait for negative rounds too...
        if self.bracket.finished:
            return winner
        return 0

    def Status_Participating(self, who):
        # check if you're assigned to vote in this bracket
        judge = self.Get_Judge(who)
        if not judge:
            return False
        return True 
        #return judge.decisions < judge.eligable

    def Status_Wait(self, who):
        # check if the voting assignments are all distributed for this round 
        # should already know they are a judge (they would have got non-part msg)
        # this depends on cleanup running first...
        try:
            judge = self.Get_Judge(who)
            bout = self.Bout_Assignment(judge)
            if bout:
                return False
            return True
        except:
            return True 

    def Status_Vote_Ready(self, who):
        # make sure they have a bout assigned and there's not already a winner
        try:
            judge = self.Get_Judge(who)
            bout = self.Bout_Assignment(judge)
        except:
            return False
        return (bout.winner == None)

    def Status_Vote_Done(self, who):
        if self.bracket.finished:
            return False
        return True
        #in_hole = self.bracket.bout_set.filter(judge__isnull=True, winner__isnull=True)
        pass

    def Vote_Choices(self, who):
        judge = self.Get_Judge(who)
        if not judge:
            return [('some_url', "<a href='" + 'some_url' + "'>not a judge for this bracket!</a>"), ('another_url',"<a href='" + 'another_url' + "'>not a judge for this bracket!</a>")] 
        bout = self.Bout_Assignment(judge)
        if not bout:
            return [('some_url', "<a href='" + 'some_url' + "'>bout not ready for this bracket!</a>"), ('another_url',"<a href='" + 'another_url' + "'>bout not ready for this bracket!</a>")] 
        return [(bout.compA.game, "<a href='" + bout.compA.game + "' class='data-log-external' target='_blank'>submission 1 (click to review)</a>"), (bout.compB.game,"<a href='" + bout.compB.game + "' class='data-log-external' target='_blank'>submission 2 (click to review)</a>")] 

       
    def Bout_Assignment(self, judge):
        # check if bout assignment already exists
        on_deck = self.bracket.bout_set.filter(judge=judge)
        if len(on_deck) > 0:
            return on_deck[0]
        # or try to make a new bout assignment
        in_hole = self.bracket.bout_set.filter(judge__isnull=True, winner__isnull=True)
        if len(in_hole) > 0:
            bout = in_hole[0]
            bout.judge = judge
            bout.btime = datetime.now()
            bout.save()
            return bout
        return False

    def Bout_Id(self, who):
        judge = self.Get_Judge(who)
        if not judge:
            return None 
        bout = self.Bout_Assignment(judge)
        if not bout:
            return 0
        return bout.id

    def Record_Vote(self, bout_id, who, game):
        try:
            # make sure the vote is still assigned to them, may have timed out!
            bout = Bout.objects.get(id=bout_id)
            winner = Competitor.objects.get(bracket=self.bracket, game=game)
            judge = Judge.objects.get(bracket=self.bracket, name=who)
        except: 
            # must have timed out!
            return
        if winner == bout.compA:
            looser = bout.compB
        else:
            looser = bout.compA
        # set record the competitors stats
        judge.decisions += 1
        judge.save()
        looser.losses += 1
        looser.save()
        winner.wins += 1 
        winner.save()
        # record the bout winner
        bout.winner = winner
        bout.save()

class Single_Elimination(Base_Tourney):

    def __init__(self, **kwargs):
        super(Single_Elimination, self).__init__(**kwargs)
        pass

    def RePair(self, who):
        bround = self.Get_Next_Round_Number()
        comp_res = Competitor.objects.filter(bracket=self.bracket, losses=0).extra(order_by = ['byes'])
        competitors = [x for x in comp_res]
        # check if a winner has already been found...
        if len(competitors) == 1:
            # this only needs to happen once...competitors may loose in negative rounds...no matter
            winner = competitors[0]
            winner.status = 1
            winner.save()
            # check if judgements remain and retrace or declare a winner
            judgements = self.bracket.judge_set.filter(eligable__gt=F('decisions'))
            #judgements = judgements.filter(~Q(name=who))
            """
            if len(judgements) == 0:
                self.bracket.finished = 1
                self.bracket.save()
                return # done!
            """
            # works in single elimination 
            # this creates party trash when the last person to vote submits...extra bout
            repeats = Bout.objects.filter(winner=winner, judge__isnull=False).order_by('btime')
            for ii in range(0, len(judgements)):
                bout = Bout(bracket=self.bracket, bround=-repeats[ii].bround, judge=None, compA=repeats[ii].compA, compB=repeats[ii].compB)
                bout.save() 
            return
        # handle the bye
        if len(competitors) % 2 > 0:
            bye = competitors[0]
            competitors = competitors[1:]
            btime = datetime.now()
            bout = Bout(bracket=self.bracket, bround=bround, judge=None, compA=bye, compB=bye, winner=bye, btime=btime)
            bout.save()
            bye.byes += 1
            bye.wins += 1
            bye.save()
        comps = []
        while(len(competitors) > 1):
            one = competitors.pop()
            two = competitors.pop()
            comps.append([one,two])
        for cc in comps:
            bout = Bout(bracket=self.bracket, bround=bround, judge=None, compA=cc[0], compB=cc[1])
            bout.save() 

class Top(Base_Tourney):
    seeking = 3

    def __init__(self, **kwargs):
        super(Top, self).__init__(**kwargs)

class Top20(Top):
    seeking = 3

    def __init__(self, **kwargs):
        super(Top20, self).__init__(**kwargs)

class Top10(Top):
    seeking = 10

    def __init__(self):
        pass

class Genetic(Base_Tourney):

    def __init__(self):
        pass

class Absolute_Order(Base_Tourney):

    def __init__(self):
        pass

    def Advancing(self):
        # decide if selection or elimination round
        # find everyone who is advancing to the next round
        # set status of those selected/eliminated
        pass 

class Swiss_Style(Base_Tourney):

    def __init__(self):
        pass




